"""Thin wrapper around the Google Gemini API (google-genai SDK). One provider for the build.

Callers build provider-neutral messages:
    [{"role": "user" | "assistant", "content": str | [text / media parts]}]
and `call()` converts them to Gemini `contents`. Everything else in TsekMate (prompts, Pydantic validation, score
recompute, routing) is provider-independent.
"""
from __future__ import annotations

import json
import logging
import os
import re
from functools import lru_cache

from ..config import get_settings

log = logging.getLogger("tsekmate.llm")


class LLMUnavailable(RuntimeError):
    """No API key configured: live AI calls are off."""


class LLMError(RuntimeError):
    """A provider error with a message that is safe to show a teacher (never contains the key).

    `status` is the HTTP status the TsekMate API returns for it.
    """

    def __init__(self, message: str, status: int = 502) -> None:
        super().__init__(message)
        self.status = status


_KEY_PATTERN = re.compile(r"AIza[0-9A-Za-z_\-]{20,}")


def _safe(text: str) -> str:
    """Strip anything that looks like a Google API key and keep messages short."""
    return _KEY_PATTERN.sub("[redacted]", text or "")[:300]


@lru_cache(maxsize=4)
def _client_for(api_key: str):
    from google import genai
    from google.genai import types

    retry = types.HttpRetryOptions(
        attempts=int(os.getenv("GEMINI_RETRY_ATTEMPTS", "3")),  # includes the first try
        initial_delay=2.0,
        max_delay=30.0,
        http_status_codes=[429, 500, 502, 503, 504],
    )
    return genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=180_000, retry_options=retry))


def _client():
    s = get_settings()
    if not s.gemini_api_key:
        raise LLMUnavailable("GEMINI_API_KEY is not set, so live AI calls are off. Set it in .env (or use DEMO_MODE for the sample set).")
    return _client_for(s.gemini_api_key)


def _to_contents(messages: list[dict]):
    from google.genai import types

    contents = []
    for m in messages:
        role = "model" if m["role"] == "assistant" else "user"
        content = m["content"]
        blocks = [{"type": "text", "text": content}] if isinstance(content, str) else content
        parts = []
        for b in blocks:
            if b["type"] == "text":
                parts.append(types.Part.from_text(text=b["text"]))
            elif b["type"] == "media":
                parts.append(types.Part.from_bytes(data=b["data"], mime_type=b["mime_type"]))
            else:
                raise ValueError(f"Unknown message part type: {b['type']}")
        contents.append(types.Content(role=role, parts=parts))
    return contents


def _map_api_error(e, model: str) -> LLMError:
    code = getattr(e, "code", None) or 0
    text = f"{getattr(e, 'status', '')} {getattr(e, 'message', '')} {e}"
    if "API_KEY_INVALID" in text or "API key not valid" in text or code == 401:
        return LLMError("The Gemini API key was rejected. Check GEMINI_API_KEY in .env and restart the API.", 503)
    if code == 403:
        return LLMError("This Gemini API key is not allowed to use the Generative Language API (permission denied). Check the key's restrictions in Google AI Studio.", 503)
    if code == 404:
        return LLMError(f"Gemini model '{model}' was not found or is not available to this key. Check GEMINI_MODEL in .env.", 503)
    if code == 429:
        return LLMError(
            "Gemini rate limit or free-tier quota reached. Wait a minute and try again; daily free-tier quotas reset at midnight Pacific time.",
            429,
        )
    if code >= 500:
        return LLMError("Gemini is temporarily unavailable. Try again in a moment.", 503)
    if code == 400:
        return LLMError(f"Gemini rejected the request: {_safe(getattr(e, 'message', '') or str(e))}", 502)
    return LLMError(f"Gemini request failed ({code}): {_safe(getattr(e, 'message', '') or str(e))}", 502)


def call(messages: list[dict], max_tokens: int = 16000, system: str | None = None, json_output: bool = True) -> str:
    """Single generate_content call. Returns the response text (JSON text when json_output is True).

    Raises LLMUnavailable (no key), LLMError (provider error, safe message), or ValueError (output cut off or empty),
    which the grader treats like malformed output and retries once.
    """
    from google.genai import errors, types

    s = get_settings()
    client = _client()
    config = types.GenerateContentConfig(
        system_instruction=system,
        # Thinking tokens count toward the output limit on Gemini 2.5 models, so keep a floor.
        max_output_tokens=max(max_tokens, 8192),
        response_mime_type="application/json" if json_output else None,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    budget = os.getenv("GEMINI_THINKING_BUDGET")
    if budget not in (None, ""):
        config.thinking_config = types.ThinkingConfig(thinking_budget=int(budget))
    try:
        resp = client.models.generate_content(model=s.gemini_model, contents=_to_contents(messages), config=config)
    except errors.APIError as e:
        err = _map_api_error(e, s.gemini_model)
        log.warning("Gemini API error %s: %s", getattr(e, "code", "?"), err)
        raise err from None
    except Exception as e:  # network errors, timeouts
        log.warning("Gemini request failed: %s", type(e).__name__)
        raise LLMError(f"Could not reach Gemini ({type(e).__name__}). Check the network and try again.", 503) from None

    feedback = getattr(resp, "prompt_feedback", None)
    if feedback is not None and getattr(feedback, "block_reason", None):
        raise LLMError(f"Gemini blocked this request ({feedback.block_reason}). Please grade this paper by hand.", 422)
    if not resp.candidates:
        raise ValueError("Gemini returned no candidates.")
    cand = resp.candidates[0]
    reason = str(getattr(cand, "finish_reason", "") or "")
    text = "".join(p.text for p in (cand.content.parts if cand.content and cand.content.parts else []) if getattr(p, "text", None) and not getattr(p, "thought", False))
    if "MAX_TOKENS" in reason:
        raise ValueError("The model output was cut off (max output tokens). " + text[-200:])
    if any(r in reason for r in ("SAFETY", "BLOCKLIST", "PROHIBITED", "SPII", "RECITATION")):
        raise LLMError(f"Gemini stopped the response ({reason.split('.')[-1]}). Please grade this paper by hand.", 422)
    if not text.strip():
        raise ValueError(f"Gemini returned an empty response (finish reason {reason or 'unknown'}).")
    return text


def image_block(data: bytes, media_type: str) -> dict:
    """The actual image bytes; converted to a Gemini inline-data part in call()."""
    return {"type": "media", "mime_type": media_type, "data": data}


def pdf_block(data: bytes) -> dict:
    return {"type": "media", "mime_type": "application/pdf", "data": data}


def extract_json(text: str) -> dict:
    """Parse the JSON object in a model reply (tolerates accidental code fences)."""
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    start, end = t.find("{"), t.rfind("}")
    if start < 0 or end < start:
        raise ValueError("No JSON object found in the model reply.")
    return json.loads(t[start : end + 1])


def render(template: str, **values: str) -> str:
    for k, v in values.items():
        template = template.replace("{{" + k + "}}", str(v))
    return template
