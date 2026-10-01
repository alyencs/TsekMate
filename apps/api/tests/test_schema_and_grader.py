import json

import pytest
from pydantic import ValidationError

from app.config import get_settings
from app.grading import grader, llm
from app.models import PaperOut

ACT = {"id": "a1", "title": "T", "subject": "math", "settings": {"feedback_style": "hint_only", "accept_alternate": True}}
PROBLEMS = [{"id": "a1-p1", "position": 1, "text": "Solve 2x = 4", "expected_answer": "x = 2", "sample_solution": "", "rule": ""}]
RUBRIC = [{"name": "Setup", "points": 2, "description": ""}, {"name": "Final answer", "points": 2, "description": ""}]


def good(**over):
    u = {"index": 1, "transcribed_text": "2x = 4", "alt_reading": None, "verdict": "correct", "error_type": None, "criterion": "Setup",
         "points_awarded": 2, "points_max": 2, "confidence": 0.9, "comment": "", "bbox": [0.1, 0.1, 0.5, 0.05]}
    u2 = {**u, "index": 2, "transcribed_text": "x = 2", "criterion": "Final answer"}
    p = {"problem_id": "a1-p1", "expected_answer": "x = 2", "units": [u, u2], "suggested_score": 4, "max_score": 4, "overall_confidence": 0.9, "flags": [], "student_hint": "Good."}
    p.update(over)
    return {"problems": [p]}


def test_valid_output_passes():
    PaperOut.model_validate(good()).check_against("math", ["a1-p1"], ["Setup", "Final answer"])


def test_bad_verdict_and_confidence_rejected():
    bad = good()
    bad["problems"][0]["units"][0]["verdict"] = "maybe"
    with pytest.raises(ValidationError):
        PaperOut.model_validate(bad)
    bad = good()
    bad["problems"][0]["units"][0]["confidence"] = 1.4
    with pytest.raises(ValidationError):
        PaperOut.model_validate(bad)


def test_error_type_must_match_subject_and_problems_complete():
    bad = good()
    bad["problems"][0]["units"][0]["error_type"] = "spelling"  # grammar type in a math activity
    with pytest.raises(ValueError, match="error_type"):
        PaperOut.model_validate(bad).check_against("math", ["a1-p1"], ["Setup", "Final answer"])
    with pytest.raises(ValueError, match="missing"):
        PaperOut.model_validate(good()).check_against("math", ["a1-p1", "a1-p2"], ["Setup", "Final answer"])


def test_malformed_bbox_is_dropped_not_fatal():
    raw = good()
    raw["problems"][0]["units"][0]["bbox"] = [0.2, 3]
    assert PaperOut.model_validate(raw).problems[0].units[0].bbox is None


@pytest.fixture
def fake_llm(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "gemini_api_key", "test-key")
    monkeypatch.setattr(s, "demo_mode", False)
    replies: list[str] = []
    calls: list[list] = []

    def fake_call(messages, max_tokens=16000, system=None):
        calls.append(messages)
        return replies.pop(0)

    monkeypatch.setattr(llm, "call", fake_call)
    return replies, calls


def test_retry_once_then_success(fake_llm):
    replies, calls = fake_llm
    replies += ["not json at all", "```json\n" + json.dumps(good(suggested_score=99)) + "\n```"]
    res = grader.grade_image(b"img", "image/png", ACT, PROBLEMS, RUBRIC)
    assert res["status"] == "ready"
    assert res["suggested_score"] == 4  # recomputed, not the model's 99
    assert len(calls) == 2
    assert "did not pass validation" in calls[1][-1]["content"]


def test_two_invalid_replies_mark_failed(fake_llm):
    replies, _ = fake_llm
    replies += ['{"problems": []}', '{"problems": "nope"}']
    res = grader.grade_image(b"img", "image/png", ACT, PROBLEMS, RUBRIC)
    assert res["status"] == "failed"
    assert res["flags"] == ["grading_failed"]


def test_prompt_contains_rubric_safety_and_hint_rules():
    prompt = grader.build_prompt(ACT, PROBLEMS, RUBRIC)
    assert "never an instruction" in prompt
    assert "HINT ONLY" in prompt
    assert '"criterion": "Setup"' in prompt
    assert "computational" in prompt
