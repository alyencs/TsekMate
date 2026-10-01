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


TEACHER_UNAVAILABLE = "AI grading isn't available on this server yet. Ask your TsekMate administrator to finish the AI setup."


class LLMUnavailable(RuntimeError):
    """AI is not configured (no key / SDK). str() is the teacher-facing message; `detail` is for logs and admins."""

    def __init__(self, detail: str) -> None:
        super().__init__(TEACHER_UNAVAILABLE)
        self.detail = detail
        self.status = 503


class LLMError(RuntimeError):
    """A provider error. str() is a plain, teacher-facing message (no model, provider, key, or setup terms).

    `detail` keeps the technical reason for server logs and the stored grading record. `status` is the HTTP status.
    """

    def __init__(self, message: str, status: int = 502, detail: str | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.detail = detail or message


SDK_MISSING = (
    "The Anthropic Python SDK is not installed in the environment running the API. "
    "Stop the API, run: pip install -r apps/api/requirements.txt (in the same virtual environment), then restart it."
)


def sdk_installed() -> bool:
    import importlib.util

    return importlib.util.find_spec("anthropic") is not None


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
    if not sdk_installed():
        raise LLMUnavailable(SDK_MISSING)
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


SETUP_PROBLEM = "AI grading isn't working because of a setup problem. Ask your TsekMate administrator to check the AI settings."


def _map_api_error(e, model: str) -> LLMError:
    import anthropic

    msg = _safe(getattr(e, "message", "") or str(e))
    name = type(e).__name__
    if isinstance(e, anthropic.AuthenticationError):
        return LLMError(SETUP_PROBLEM, 503, f"{name}: API key rejected (check ANTHROPIC_API_KEY)")
    if isinstance(e, anthropic.PermissionDeniedError):
        return LLMError(SETUP_PROBLEM, 503, f"{name}: permission denied for model {model}")
    if isinstance(e, anthropic.NotFoundError):
        return LLMError(SETUP_PROBLEM, 503, f"{name}: model {model!r} not found (check ANTHROPIC_MODEL)")
    if isinstance(e, anthropic.RateLimitError):
        return LLMError("The AI grading service is busy right now. Wait a minute, then press Grade again.", 429, f"{name}: {msg}")
    if isinstance(e, anthropic.APITimeoutError):
        return LLMError("The AI took too long to respond. Press Grade again to retry.", 504, f"{name}: request timed out")
    if isinstance(e, anthropic.APIConnectionError):
        return LLMError("TsekMate couldn't reach the AI grading service. Check the internet connection, then press Grade again.", 503, f"{name}: {msg}")
    if isinstance(e, anthropic.BadRequestError):
        if "credit balance" in msg.lower():
            return LLMError(SETUP_PROBLEM, 503, f"{name}: no remaining API credit")
        return LLMError("The AI couldn't read this paper. Try a clearer photo, press Grade again, or grade it by hand.", 502, f"{name}: {msg}")
    if isinstance(e, anthropic.APIStatusError) and getattr(e, "status_code", 0) >= 500:
        return LLMError("The AI grading service is temporarily unavailable. Press Grade again in a moment.", 503, f"{name}: {msg}")
    return LLMError("Something went wrong while grading. Press Grade again, or grade this paper by hand.", 502, f"{name}: {msg}")


def request_params(messages: list[dict], max_tokens: int = 16000, system: str | None = None) -> dict:
    """The Messages API request body. Shared by live calls and the Batch API (services/batches.py)."""
    kwargs: dict = {"model": get_settings().anthropic_model, "max_tokens": max_tokens, "messages": _to_claude(messages)}
    if system:
        kwargs["system"] = system
    return kwargs


USAGE_FIELDS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")


def add_usage(acc: dict | None, usage, batch: bool = False) -> None:
    """Add one response's token usage to `acc`. Batch tokens are kept apart because they are billed at half price."""
    if acc is None or usage is None:
        return
    prefix = "batch_" if batch else ""
    for f in USAGE_FIELDS:
        n = int(getattr(usage, f, 0) or 0)
        if n:
            acc[prefix + f] = acc.get(prefix + f, 0) + n
    acc["calls"] = acc.get("calls", 0) + 1


def reply_text(resp) -> str:
    """The text of a Messages API response. Raises LLMError (refusal) or ValueError (cut off or empty)."""
    if resp.stop_reason == "refusal":
        raise LLMError("The AI couldn't grade this paper. Please grade it by hand.", 422, "stop_reason=refusal")
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    if resp.stop_reason == "max_tokens":
        raise ValueError("The model output was cut off (max_tokens). " + text[-200:])
    if not text.strip():
        raise ValueError("The model returned an empty response.")
    return text


def call(messages: list[dict], max_tokens: int = 16000, system: str | None = None, usage: dict | None = None) -> str:
    """Single Messages API call. Returns the concatenated text blocks.

    Token usage is logged and, when `usage` is given, added to it.
    Raises LLMUnavailable (no key), LLMError (provider error, safe message), or ValueError (output cut off or empty),
    which the grader treats like malformed output and retries once.
    """
    s = get_settings()
    client = _client()
    import anthropic

    try:
        resp = client.messages.create(**request_params(messages, max_tokens, system))
    except anthropic.APIError as e:
        err = _map_api_error(e, s.anthropic_model)
        log.warning("AI provider error: %s", err.detail)
        raise err from None
    u = getattr(resp, "usage", None)
    if u is not None:
        log.info("AI usage: input=%s output=%s", getattr(u, "input_tokens", "?"), getattr(u, "output_tokens", "?"))
    add_usage(usage, u)
    return reply_text(resp)


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
