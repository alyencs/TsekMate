"""Grade again, identity matching after grading, AI rubric drafts, notifications, settings, profile, roster."""
import io
import json
import time

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import get_settings
from app.grading import llm

A = "act-linear-eq-quiz1"


@pytest.fixture(scope="module")
def client():
    from app.main import app
    from app.seed import reset_and_seed
    from app.store import get_store

    with TestClient(app) as c:
        reset_and_seed(get_store())  # independent of what other test modules changed
        yield c


def paper_reply(activity_problems, name="Maria Santos", sid="2026-002", conf=0.95):
    probs = []
    for p in activity_problems:
        units = [
            {"index": i + 1, "transcribed_text": t, "alt_reading": None, "verdict": "correct", "error_type": None, "criterion": c,
             "points_awarded": pts, "points_max": pts, "confidence": 0.95, "comment": "", "bbox": None}
            for i, (c, t, pts) in enumerate([("Setup", "a", 2), ("Method", "b", 3), ("Computation", "c", 3), ("Final answer", "d", 2)])
        ]
        probs.append({"problem_id": p["id"], "expected_answer": p["expected_answer"], "units": units, "suggested_score": 10, "max_score": 10,
                      "overall_confidence": 0.95, "flags": [], "student_hint": "Good work."})
    return json.dumps({"student_name": name, "student_id": sid, "identity_confidence": conf, "problems": probs})


def wait_done(client, activity_id):
    for _ in range(100):
        p = client.get(f"/api/activities/{activity_id}/grading-progress").json()
        if not p["running"]:
            return p
        time.sleep(0.05)
    raise AssertionError("grading did not finish")


def upload(client):
    buf = io.BytesIO()
    Image.new("RGB", (400, 500), "white").save(buf, format="PNG")
    r = client.post(f"/api/activities/{A}/submissions", files=[("files", ("p.png", buf.getvalue(), "image/png"))])
    assert r.status_code == 201
    return r.json()[0]["id"]


def test_failed_paper_can_be_graded_again_and_is_matched_by_name(client, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "demo_mode", False)
    assert client.delete("/api/submissions/sub-math-2026-002").status_code == 204
    sid = upload(client)
    # 1st attempt: the provider is rate limited -> failed, safe reason, retry offered
    monkeypatch.setattr(s, "anthropic_api_key", "sk-ant-test")

    def rate_limited(*a, **k):
        raise llm.LLMError("Claude rate limit reached. Wait a minute and press Grade again.", 429)

    monkeypatch.setattr(llm, "call", rate_limited)
    client.post(f"/api/activities/{A}/grade")
    wait_done(client, A)
    d = client.get(f"/api/submissions/{sid}").json()
    assert d["status"] == "failed" and "rate limit" in d["ai_result"]["failure_reason"] and d["student_id"] is None
    # Grade again: succeeds; the name on the paper matches the roster
    problems = client.get(f"/api/activities/{A}").json()["problems"]
    monkeypatch.setattr(llm, "call", lambda *a, **k: paper_reply(problems, sid=None))
    r = client.post(f"/api/submissions/{sid}/regrade")
    assert r.status_code == 200 and r.json()["total"] == 1
    wait_done(client, A)
    d = client.get(f"/api/submissions/{sid}").json()
    assert d["status"] == "ready" and d["student_id"] == "2026-002" and d["student_name"] == "Maria Santos"
    assert d["identity"]["method"] == "name" and d["ai_result"]["prompt_version"] == "v1.1"
    # a graded paper cannot be "graded again" (only failed / not graded ones)
    assert client.post(f"/api/submissions/{sid}/regrade").status_code == 409
    n = client.get("/api/notifications").json()
    titles = [x["title"] for x in n["items"]]
    assert any("Grade again succeeded" in t for t in titles) and any("could not be graded" in t for t in titles)


def test_missing_name_still_grades_and_needs_review(client, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "anthropic_api_key", "sk-ant-test")
    monkeypatch.setattr(s, "demo_mode", False)
    assert client.delete("/api/submissions/sub-math-2026-030").status_code == 204
    sid = upload(client)
    problems = client.get(f"/api/activities/{A}").json()["problems"]
    monkeypatch.setattr(llm, "call", lambda *a, **k: paper_reply(problems, name=None, sid=None, conf=0))
    client.post(f"/api/activities/{A}/grade")
    wait_done(client, A)
    d = client.get(f"/api/submissions/{sid}").json()
    assert d["ai_result"]["suggested_score"] == 50  # graded in full
    assert d["student_id"] is None and d["identity"]["status"] == "unidentified"
    assert d["status"] == "needs_review"  # high grading confidence, but the teacher must pick the student
    q = client.get(f"/api/activities/{A}/queue?tab=needs_review").json()
    assert "Student not identified" in next(r for r in q["rows"] if r["submission_id"] == sid)["chips"]
    assert client.post(f"/api/submissions/{sid}/approve").status_code == 409
    d = client.patch(f"/api/submissions/{sid}/student", json={"student_id": "2026-030"}).json()
    assert d["student_name"] == "Bryan Valdez" and d["status"] == "ready"
    assert client.post(f"/api/submissions/{sid}/approve").json()["submission"]["status"] == "approved"


def test_roster_tracks_not_submitted(client):
    r = client.get(f"/api/activities/{A}/roster").json()
    by = {x["student_id"]: x for x in r["students"]}
    assert len(by) == 40
    assert by["2026-039"]["status"] == "Not submitted" and by["2026-039"]["student_name"] == "Kathleen Uy"
    g = client.get(f"/api/activities/{A}/gradebook").json()
    assert any(row["student_id"] is None and row["status"] == "Student not identified" for row in g["rows"])
    assert any(row["student_id"] == "2026-040" and row["status"] == "Not submitted" for row in g["rows"])


def test_ai_rubric_is_a_normalized_draft(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "sk-ant-test")
    reply = {"criteria": [{"name": "Setup", "description": "Sets up", "points": 3}, {"name": "Method", "description": "m", "points": 3},
                          {"name": "setup", "description": "dup", "points": 1}, {"name": "Answer", "description": "a", "points": 3}]}
    monkeypatch.setattr(llm, "call", lambda *a, **k: json.dumps(reply))
    body = {"subject": "math", "title": "Quiz", "problems": [{"text": "Solve 2x = 4", "expected_answer": "x = 2"}], "points_per_problem": 12}
    r = client.post("/api/rubric/generate", json=body).json()
    assert r["draft"] is True and [c["name"] for c in r["criteria"]] == ["Setup", "Method", "Answer"]
    assert sum(c["points"] for c in r["criteria"]) == 12
    monkeypatch.setattr(llm, "call", lambda *a, **k: '{"criteria": [{"name": "Only one", "points": 10}]}')
    assert client.post("/api/rubric/generate", json=body).status_code == 502
    assert client.post("/api/rubric/generate", json={"subject": "math"}).status_code == 400


def test_notifications_read_state(client):
    n = client.get("/api/notifications").json()
    assert n["unread"] > 0 and all({"title", "body", "link", "created_at", "read"} <= set(x) for x in n["items"])
    first = next(x for x in n["items"] if not x["read"])
    after = client.post(f"/api/notifications/{first['id']}/read").json()
    assert after["unread"] == n["unread"] - 1
    assert client.post("/api/notifications/read-all").json()["unread"] == 0


def test_settings_threshold_reroutes_and_profile(client):
    s = client.get("/api/settings").json()
    assert s["confidence_threshold"] == 0.75 and s["ai"]["provider"] == "Anthropic Claude"
    before = client.get(f"/api/activities/{A}/queue?tab=ready").json()["counts"]
    r = client.patch("/api/settings", json={"confidence_threshold": 0.9}).json()
    after = client.get(f"/api/activities/{A}/queue?tab=ready").json()["counts"]
    assert r["rerouted"] >= 1 and after["ready"] < before["ready"]
    client.patch("/api/settings", json={"confidence_threshold": 0.75})
    assert client.patch("/api/settings", json={"confidence_threshold": 0.2}).status_code == 422
    p = client.patch("/api/profile", json={"name": "Prof. Ana Reyes-Lim"}).json()
    assert p["name"] == "Prof. Ana Reyes-Lim" and p["students"] == 75 and len(p["classes"]) == 2
    client.patch("/api/profile", json={"name": "Prof. Ana Reyes"})
