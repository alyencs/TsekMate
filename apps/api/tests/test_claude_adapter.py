"""The Claude provider seam (app/grading/llm.py): request conversion, response handling, safe error messages."""
import base64
from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from app.config import get_settings
from app.grading import llm

REQ = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


def status_error(cls, code, message):
    return cls(message, response=httpx2.Response(code, request=REQ), body={"error": {"message": message}})


class FakeMessages:
    def __init__(self, resp=None, exc=None):
        self.resp, self.exc, self.calls = resp, exc, []

    def create(self, **kw):
        self.calls.append(kw)
        if self.exc:
            raise self.exc
        return self.resp


def reply(text="{}", stop="end_turn"):
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)], stop_reason=stop)


@pytest.fixture
def fake(monkeypatch):
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "sk-ant-test")

    def install(resp=None, exc=None):
        m = FakeMessages(resp, exc)
        monkeypatch.setattr(llm, "_client", lambda: SimpleNamespace(messages=m))
        return m

    return install


def test_missing_key(monkeypatch):
    monkeypatch.setattr(get_settings(), "anthropic_api_key", None)
    with pytest.raises(llm.LLMUnavailable) as e:
        llm.call([{"role": "user", "content": "hi"}])
    assert "ANTHROPIC_API_KEY" in e.value.detail and "ANTHROPIC" not in str(e.value)


def test_default_model_is_haiku():
    from app.config import Settings

    assert Settings().anthropic_model.startswith("claude-haiku") or get_settings().anthropic_model


def test_image_bytes_reach_claude_as_base64(fake):
    m = fake(reply('{"ok": true}'))
    img = b"\x89PNG fake image bytes"
    out = llm.call([
        {"role": "user", "content": [llm.image_block(img, "image/png"), {"type": "text", "text": "grade this"}]},
        {"role": "assistant", "content": "not json"},
        {"role": "user", "content": "fix it"},
    ])
    assert out == '{"ok": true}'
    sent = m.calls[0]
    assert sent["model"] == get_settings().anthropic_model
    block = sent["messages"][0]["content"][0]
    assert block["type"] == "image" and block["source"]["media_type"] == "image/png"
    assert base64.standard_b64decode(block["source"]["data"]) == img  # the actual photo, not a URL or filename
    assert [x["role"] for x in sent["messages"]] == ["user", "assistant", "user"]


def test_pdf_is_a_document_block(fake):
    m = fake(reply("{}"))
    llm.call([{"role": "user", "content": [llm.pdf_block(b"%PDF-1.4"), {"type": "text", "text": "x"}]}])
    assert m.calls[0]["messages"][0]["content"][0]["type"] == "document"


def test_truncated_empty_and_refusal(fake):
    fake(reply('{"problems": [', stop="max_tokens"))
    with pytest.raises(ValueError, match="cut off"):
        llm.call([{"role": "user", "content": "x"}])
    fake(reply("   "))
    with pytest.raises(ValueError, match="empty"):
        llm.call([{"role": "user", "content": "x"}])
    fake(reply("", stop="refusal"))
    with pytest.raises(llm.LLMError) as e:
        llm.call([{"role": "user", "content": "x"}])
    assert e.value.status == 422


TECHNICAL = ("ANTHROPIC", "Claude", "claude", "API", "model", "SDK", "pip ", "SECRET")


def teacher_safe(msg: str) -> bool:
    return not any(t in msg for t in TECHNICAL)


@pytest.mark.parametrize(
    "exc,status,needle,detail",
    [
        (status_error(anthropic.AuthenticationError, 401, "invalid x-api-key sk-ant-api03-SECRETSECRET"), 503, "administrator", "ANTHROPIC_API_KEY"),
        (status_error(anthropic.PermissionDeniedError, 403, "forbidden"), 503, "administrator", "permission"),
        (status_error(anthropic.NotFoundError, 404, "model: claude-x"), 503, "administrator", "ANTHROPIC_MODEL"),
        (status_error(anthropic.RateLimitError, 429, "rate_limit_error"), 429, "busy", "RateLimitError"),
        (status_error(anthropic.InternalServerError, 529, "overloaded_error"), 503, "temporarily", "overloaded"),
        (status_error(anthropic.BadRequestError, 400, "Your credit balance is too low"), 503, "administrator", "credit"),
        (status_error(anthropic.BadRequestError, 400, "messages.0: bad image key=sk-ant-api03-SECRETSECRET"), 502, "couldn't read this paper", "bad image"),
        (anthropic.APITimeoutError(request=REQ), 504, "too long", "timed out"),
        (anthropic.APIConnectionError(request=REQ), 503, "couldn't reach", "APIConnectionError"),
    ],
)
def test_errors_map_to_teacher_messages_and_keep_detail_for_logs(fake, exc, status, needle, detail):
    fake(exc=exc)
    with pytest.raises(llm.LLMError) as e:
        llm.call([{"role": "user", "content": "x"}])
    assert e.value.status == status
    assert needle in str(e.value) and teacher_safe(str(e.value))  # what a teacher may see
    assert detail in e.value.detail and "SECRET" not in e.value.detail  # server logs only, key redacted


def test_missing_sdk_gives_install_instructions_to_admins_only(monkeypatch):
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "sk-ant-test")
    monkeypatch.setattr(llm, "sdk_installed", lambda: False)
    with pytest.raises(llm.LLMUnavailable) as e:
        llm.call([{"role": "user", "content": "x"}])
    assert "pip install -r apps/api/requirements.txt" in e.value.detail and teacher_safe(str(e.value))
