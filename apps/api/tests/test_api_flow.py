import io

import pytest
from fastapi.testclient import TestClient

from tests.helpers import blank, sign_in
from PIL import Image


@pytest.fixture(scope="module")
def client():
    from app.main import app

    with TestClient(app) as c:
        sign_in(c)
        yield c


A = "act-linear-eq-quiz1"


def test_seed_reproduces_mockup_numbers(client):
    d = client.get("/api/dashboard").json()
    assert d["awaiting_review"]["value"] == 12
    assert d["flagged"]["value"] == 9
    assert d["approved_today"]["value"] >= 26
    assert d["queue_badge"] == 21
    q = client.get(f"/api/activities/{A}/queue?tab=needs_review").json()
    assert q["counts"] == {"needs_review": 9, "ready": 3, "approved": 26, "all": 38}
    assert [r["student_id"] for r in q["rows"][:3]] == ["2026-014", "2026-002", "2026-009"]
    confs = [r["confidence"] for r in q["rows"]]
    assert confs == sorted(confs)
    s = client.get(f"/api/activities/{A}/class-summary").json()
    assert {e["error_type"]: e["count"] for e in s["errors_by_type"]} == {"computational": 12, "conceptual": 18, "notation": 5, "presentation": 3}
    assert s["most_missed_criterion"] == "Method"
    assert s["misconceptions"][0]["count"] == 14


def test_review_edit_and_approve(client):
    sid = "sub-math-2026-014"
    d = client.get(f"/api/submissions/{sid}").json()
    p2 = next(p for p in d["ai_result"]["problems"] if p["problem_id"].endswith("-p2"))
    assert p2["suggested_score"] == 5
    # The breakdown is the activity rubric: Setup 2 + Method 3 + Computation 3 + Final answer 2 = 10.
    assert [(c["name"], c["points"]) for c in p2["criteria_scores"]] == [("Setup", 2), ("Method", 3), ("Computation", 3), ("Final answer", 2)]
    assert p2["max_score"] == 10 and p2["final_score"] == sum(c["awarded"] for c in p2["criteria_scores"])
    key = f"{p2['problem_id']}::Method"
    r = client.patch(f"/api/submissions/{sid}/review", json={"criterion_scores": {key: 2}, "feedback": {p2["problem_id"]: "Check line 2."}})
    assert r.status_code == 200
    assert any(e["field"] == f"criterion.{key}" for e in r.json()["review"]["edit_log"])
    p2 = next(p for p in r.json()["ai_result"]["problems"] if p["problem_id"] == p2["problem_id"])
    assert p2["final_score"] == 6 and next(c for c in p2["criteria_scores"] if c["name"] == "Method")["edited"]
    bad = client.patch(f"/api/submissions/{sid}/review", json={"criterion_scores": {key: 3.5}})  # over the criterion's 3
    assert bad.status_code == 409 and "0 to 3" in bad.json()["detail"]
    assert client.patch(f"/api/submissions/{sid}/review", json={"criterion_scores": {f"{p2['problem_id']}::Neatness": 1}}).status_code == 409
    a = client.post(f"/api/submissions/{sid}/approve").json()
    assert a["submission"]["status"] == "approved"
    g = client.get(f"/api/activities/{A}/gradebook").json()
    assert g["rows"][0]["student_id"] == "2026-014" and g["rows"][0]["just_approved"]
    assert g["rows"][0]["scores"][1] == 6 and g["rows"][0]["edited"][1]
    assert client.delete(f"/api/submissions/{sid}").status_code == 409


def test_upload_starts_unidentified_grading_without_key_fails_safely_and_teacher_assigns(client, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "anthropic_api_key", None)
    monkeypatch.setattr(get_settings(), "demo_mode", False)
    assert client.delete("/api/submissions/sub-math-2026-002").status_code == 204
    buf = io.BytesIO()
    blank((400, 500)).save(buf, format="PNG")
    r = client.post(f"/api/activities/{A}/submissions", files=[("files", ("p.png", buf.getvalue(), "image/png"))])
    assert r.status_code == 201
    sid = r.json()[0]["id"]
    assert r.json()[0]["student_id"] is None  # identified later from the paper, or by the teacher
    from app.services import jobs
    from app.store import get_store

    get_store().update("submissions", sid, {"status": "grading", "grading_attempt": "test"})  # what jobs.start does

    res = jobs.grade_submission(get_store(), sid)
    assert res["status"] == "failed" and res["flags"] == ["grading_failed"]
    d = client.get(f"/api/submissions/{sid}").json()
    reason = d["ai_result"]["failure_reason"]
    assert d["student_id"] is None and "administrator" in reason and "ANTHROPIC" not in reason  # teacher-facing only
    assert client.post(f"/api/submissions/{sid}/approve").status_code == 409  # graded? no. and no student
    taken = client.patch(f"/api/submissions/{sid}/student", json={"student_id": "2026-001"})
    assert taken.status_code == 409  # 2026-001 already has a paper
    ok = client.patch(f"/api/submissions/{sid}/student", json={"student_id": "2026-002"}).json()
    assert ok["student_id"] == "2026-002" and ok["student_name"] == "Maria Santos" and ok["identity"]["method"] == "teacher"


def test_unsupported_file_rejected(client):
    r = client.post(f"/api/activities/{A}/submissions", files=[("files", ("x.txt", b"hello", "text/plain"))])
    assert r.status_code == 415
