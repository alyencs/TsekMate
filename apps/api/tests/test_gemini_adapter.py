"""The Gemini provider seam (app/grading/llm.py): request conversion, response handling, safe error messages."""
import pytest
from google.genai import errors, types

from app.config import get_settings
from app.grading import llm


class FakeModels:
    def __init__(self, response=None, exc=None):
        self.response, self.exc, self.calls = response, exc, []

    def generate_content(self, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        if self.exc:
            raise self.exc
        return self.response


class FakeClient:
    def __init__(self, models):
        self.models = models


def response(text="{}", finish="STOP", block=None):
    return types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(role="model", parts=[types.Part.from_text(text=text)]), finish_reason=finish)],
        prompt_feedback=types.GenerateContentResponsePromptFeedback(block_reason=block) if block else None,
    )


@pytest.fixture
def fake(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "gemini_api_key", "test-key")

    def install(resp=None, exc=None):
        models = FakeModels(resp, exc)
        monkeypatch.setattr(llm, "_client", lambda: FakeClient(models))
        return models

    return install


def test_missing_key_raises_unavailable(monkeypatch):
    monkeypatch.setattr(get_settings(), "gemini_api_key", None)
    with pytest.raises(llm.LLMUnavailable, match="GEMINI_API_KEY"):
        llm.call([{"role": "user", "content": "hi"}])


def test_image_bytes_and_roles_reach_gemini(fake):
    models = fake(response('{"ok": true}'))
    img = b"\x89PNG fake image bytes"
    msgs = [
        {"role": "user", "content": [llm.image_block(img, "image/png"), {"type": "text", "text": "grade this"}]},
        {"role": "assistant", "content": "not json"},
        {"role": "user", "content": "fix it"},
    ]
    assert llm.call(msgs, max_tokens=2000) == '{"ok": true}'
    sent = models.calls[0]
    assert sent["model"] == get_settings().gemini_model
    c = sent["contents"]
    assert [x.role for x in c] == ["user", "model", "user"]
    assert c[0].parts[0].inline_data.data == img  # the actual uploaded bytes, not a URL or filename
    assert c[0].parts[0].inline_data.mime_type == "image/png"
    assert c[0].parts[1].text == "grade this"
    assert sent["config"].response_mime_type == "application/json"
    assert sent["config"].max_output_tokens >= 8192


def test_pdf_is_sent_as_inline_pdf(fake):
    models = fake(response("{}"))
    llm.call([{"role": "user", "content": [llm.pdf_block(b"%PDF-1.4"), {"type": "text", "text": "x"}]}])
    assert models.calls[0]["contents"][0].parts[0].inline_data.mime_type == "application/pdf"


def test_truncated_or_empty_output_is_retryable(fake):
    fake(response('{"problems": [', finish="MAX_TOKENS"))
    with pytest.raises(ValueError, match="cut off"):
        llm.call([{"role": "user", "content": "x"}])
    fake(response("", finish="STOP"))
    with pytest.raises(ValueError, match="empty"):
        llm.call([{"role": "user", "content": "x"}])


def test_blocked_or_safety_stop_is_reported(fake):
    fake(response("", block="SAFETY"))
    with pytest.raises(llm.LLMError) as e:
        llm.call([{"role": "user", "content": "x"}])
    assert e.value.status == 422
    fake(response("partial", finish="SAFETY"))
    with pytest.raises(llm.LLMError):
        llm.call([{"role": "user", "content": "x"}])


@pytest.mark.parametrize(
    "code,body,status,needle",
    [
        (400, {"error": {"code": 400, "message": "API key not valid. Please pass a valid API key.", "status": "INVALID_ARGUMENT"}}, 503, "GEMINI_API_KEY"),
        (403, {"error": {"code": 403, "message": "Permission denied", "status": "PERMISSION_DENIED"}}, 503, "permission"),
        (404, {"error": {"code": 404, "message": "models/x is not found", "status": "NOT_FOUND"}}, 503, "GEMINI_MODEL"),
        (429, {"error": {"code": 429, "message": "Resource has been exhausted (e.g. check quota).", "status": "RESOURCE_EXHAUSTED"}}, 429, "quota"),
        (503, {"error": {"code": 503, "message": "The model is overloaded.", "status": "UNAVAILABLE"}}, 503, "temporarily"),
        (400, {"error": {"code": 400, "message": "Invalid value at contents. key=AIzaSyAbcdefghijklmnopqrstuvwxyz0123", "status": "INVALID_ARGUMENT"}}, 502, "rejected the request"),
    ],
)
def test_api_errors_map_to_safe_messages(fake, code, body, status, needle):
    exc = errors.ServerError(code, body) if code >= 500 else errors.ClientError(code, body)
    fake(exc=exc)
    with pytest.raises(llm.LLMError) as e:
        llm.call([{"role": "user", "content": "x"}])
    assert e.value.status == status
    assert needle in str(e.value)
    assert "AIza" not in str(e.value)


def test_grading_job_turns_provider_error_into_failed_paper(fake):
    """Quota errors during grading mark the paper failed (teacher grades by hand) instead of crashing the job."""
    from fastapi.testclient import TestClient

    from app.main import app
    from app.services import jobs
    from app.store import get_store

    with TestClient(app) as client:
        fake(exc=errors.ClientError(429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}}))
        res = jobs.grade_submission(get_store(), "sub-math-S-020")
        assert res["status"] == "failed"
        d = client.get("/api/submissions/sub-math-S-020").json()
        assert "quota" in d["ai_result"]["failure_reason"]
        # an AI text endpoint returns the provider's status and safe message to the frontend
        fake(exc=errors.ClientError(429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}}))
        r = client.post("/api/activities/act-linear-eq-quiz1/practice")
        assert r.status_code == 429 and "quota" in r.json()["detail"]
