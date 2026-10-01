"""Thin wrapper around the Anthropic SDK (one provider for the build)."""
from __future__ import annotations

import base64
import json
import re

from ..config import get_settings


class LLMUnavailable(RuntimeError):
    pass


def _client():
    s = get_settings()
    if not s.anthropic_api_key:
        raise LLMUnavailable("ANTHROPIC_API_KEY is not set, so live AI calls are off. Set it in .env (or use DEMO_MODE for the sample set).")
    import anthropic

    return anthropic.Anthropic(api_key=s.anthropic_api_key, max_retries=2, timeout=180.0)


def call(messages: list[dict], max_tokens: int = 16000, system: str | None = None) -> str:
    """Single Messages API call. Returns the concatenated text blocks."""
    import os

    s = get_settings()
    kwargs: dict = {"model": s.anthropic_model, "max_tokens": max_tokens, "messages": messages}
    if system:
        kwargs["system"] = system
    effort = os.getenv("ANTHROPIC_EFFORT", "medium")
    if effort:
        kwargs["output_config"] = {"effort": effort}
    resp = _client().messages.create(**kwargs)
    if resp.stop_reason == "refusal":
        raise RuntimeError("The model declined this request.")
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    if resp.stop_reason == "max_tokens":
        raise ValueError("The model output was cut off (max_tokens). " + text[-200:])
    return text


def image_block(data: bytes, media_type: str) -> dict:
    return {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": base64.standard_b64encode(data).decode()}}


def pdf_block(data: bytes) -> dict:
    return {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": base64.standard_b64encode(data).decode()}}


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
