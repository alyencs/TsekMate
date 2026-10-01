"""Thin wrapper around the Anthropic Claude API (official `anthropic` SDK). One provider for the build.

Callers build provider-neutral messages:
    [{"role": "user" | "assistant", "content": str | [text / media parts]}]
and `call()` converts them to Claude content blocks. Everything else in TsekMate (prompts, Pydantic validation, score
recompute, routing) is provider-independent.
"""
from __future__ import annotations

import base64
import json
import logging
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


_KEY_PATTERN = re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}")


def _safe(text: str) -> str:
    """Strip anything that looks like an Anthropic API key and keep messages short."""
    return _KEY_PATTERN.sub("[redacted]", text or "")[:300]


@lru_cache(maxsize=4)
def _client_for(api_key: str):
    import anthropic

    # The SDK retries connection errors, 408, 409, 429 and 5xx with exponential backoff.
    return anthropic.Anthropic(api_key=api_key, max_retries=3, timeout=180.0)


def _client():
    s = get_settings()
    if not s.anthropic_api_key:
        raise LLMUnavailable("ANTHROPIC_API_KEY is not set, so live AI calls are off. Set it in .env (or use DEMO_MODE for the sample set).")
    return _client_for(s.anthropic_api_key)


def _to_claude(messages: list[dict]) -> list[dict]:
    out = []
    for m in messages:
        content = m["content"]
        if isinstance(content, str):
            out.append({"role": m["role"], "content": content})
            continue
        blocks = []
        for b in content:
            if b["type"] == "text":
                blocks.append({"type": "text", "text": b["text"]})
            elif b["type"] == "media":
                data = base64.standard_b64encode(b["data"]).decode()
                kind = "document" if b["mime_type"] == "application/pdf" else "image"
                blocks.append({"type": kind, "source": {"type": "base64", "media_type": b["mime_type"], "data": data}})
            else:
                raise ValueError(f"Unknown message part type: {b['type']}")
        out.append({"role": m["role"], "content": blocks})
    return out


def _map_api_error(e, model: str) -> LLMError:
    import anthropic

    msg = _safe(getattr(e, "message", "") or str(e))
    if isinstance(e, anthropic.AuthenticationError):
        return LLMError("The Anthropic API key was rejected. Check ANTHROPIC_API_KEY in .env and restart the API.", 503)
    if isinstance(e, anthropic.PermissionDeniedError):
        return LLMError("This Anthropic API key is not allowed to use this model (permission denied). Check the key in the Claude Console.", 503)
    if isinstance(e, anthropic.NotFoundError):
        return LLMError(f"Claude model '{model}' was not found. Check ANTHROPIC_MODEL in .env.", 503)
    if isinstance(e, anthropic.RateLimitError):
        return LLMError("Claude rate limit reached. Wait a minute and press Grade again.", 429)
    if isinstance(e, anthropic.APITimeoutError):
        return LLMError("The request to Claude timed out. Press Grade again to retry.", 504)
    if isinstance(e, anthropic.APIConnectionError):
        return LLMError("Could not reach the Claude API. Check the network and press Grade again.", 503)
    if isinstance(e, anthropic.BadRequestError):
        if "credit balance" in msg.lower():
            return LLMError("The Anthropic account has no remaining credit. Add credit in the Claude Console, then press Grade again.", 503)
        return LLMError(f"Claude rejected the request: {msg}", 502)
    if isinstance(e, anthropic.APIStatusError) and getattr(e, "status_code", 0) >= 500:
        return LLMError("Claude is temporarily unavailable or overloaded. Press Grade again in a moment.", 503)
    return LLMError(f"Claude request failed: {msg}", 502)


def call(messages: list[dict], max_tokens: int = 16000, system: str | None = None) -> str:
    """Single Messages API call. Returns the concatenated text blocks.

    Raises LLMUnavailable (no key), LLMError (provider error, safe message), or ValueError (output cut off or empty),
    which the grader treats like malformed output and retries once.
    """
    import anthropic

    s = get_settings()
    client = _client()
    kwargs: dict = {"model": s.anthropic_model, "max_tokens": max_tokens, "messages": _to_claude(messages)}
    if system:
        kwargs["system"] = system
    try:
        resp = client.messages.create(**kwargs)
    except anthropic.APIError as e:
        err = _map_api_error(e, s.anthropic_model)
        log.warning("Claude API error (%s): %s", type(e).__name__, err)
        raise err from None
    if resp.stop_reason == "refusal":
        raise LLMError("Claude declined to grade this paper. Please grade it by hand.", 422)
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    if resp.stop_reason == "max_tokens":
        raise ValueError("The model output was cut off (max_tokens). " + text[-200:])
    if not text.strip():
        raise ValueError("Claude returned an empty response.")
    return text


def image_block(data: bytes, media_type: str) -> dict:
    """The actual image bytes; converted to a base64 Claude image block in call()."""
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
