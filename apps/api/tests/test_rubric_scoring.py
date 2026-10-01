"""The activity rubric is the single source of truth for every score: AI draft, review, edits, approval, gradebook, summary."""
import io
import json

import pytest
from fastapi.testclient import TestClient

from tests.helpers import blank, sign_in
from PIL import Image

from app.config import get_settings
from app.grading import llm
from app.grading.scoring import rubric_problems

A = "act-linear-eq-quiz1"


@pytest.fixture(scope="module")
def client():
    from app.main import app
    from app.seed import reset_and_seed
    from app.store import get_store

    with TestClient(app) as c:
        sign_in(c)
        reset_and_seed(get_store())
        yield c


@pytest.fixture
def ai(monkeypatch):
    """Fake Claude: replies built per call from `plan` (criterion -> (awarded, claimed points_max)); missing = skipped."""
    s = get_settings()
    monkeypatch.setattr(s, "anthropic_api_key", "test-key")
    monkeypatch.setattr(s, "demo_mode", False)
    state = {"plans": [], "calls": 0, "problems": []}

    def fake_call(messages, max_tokens=16000, system=None, usage=None):
        plan = state["plans"][min(state["calls"], len(state["plans"]) - 1)]
        state["calls"] += 1
        probs = []
        for p in state["problems"]:
            units = [
                {"index": i + 1, "transcribed_text": f"line {i + 1}", "alt_reading": None, "verdict": "correct" if got == mx else "error",
                 "error_type": None if got == mx else "computational", "criterion": name, "points_awarded": got, "points_max": mx,
                 "confidence": 0.95, "comment": "", "bbox": None}
                for i, (name, (got, mx)) in enumerate(plan.items())
            ]
            probs.append({"problem_id": p["id"], "expected_answer": p["expected_answer"], "units": units, "suggested_score": 999,
                          "max_score": 999, "overall_confidence": 0.95, "flags": [], "student_hint": "Check your work."})
        return json.dumps({"student_name": "Maria Santos", "student_id": "2026-002", "identity_confidence": 0.95, "problems": probs})

    monkeypatch.setattr(llm, "call", fake_call)
    return state


def png() -> bytes:
    buf = io.BytesIO()
    blank((300, 400)).save(buf, format="PNG")
    return buf.getvalue()


def make_activity(client, rubric, total, n_problems=1):
    cls = client.get(f"/api/activities/{A}").json()["class_name"]
    body = {"title": "Rubric check", "subject": "math", "class_name": cls, "date": "2026-10-01",
            "problems": [{"order": i + 1, "text": f"Solve {i + 2}x = {2 * (i + 2)}", "expected_answer": "x = 2"} for i in range(n_problems)],
            "rubric": [{"name": n, "description": f"About {n}", "points": p} for n, p in rubric], "rubric_total": total}
    return client.post("/api/activities", json=body)


def grade_one(client, ai, act, plans):
    from app.services import jobs
    from app.store import get_store

    ai["problems"], ai["plans"], ai["calls"] = act["problems"], plans, 0
    sid = client.post(f"/api/activities/{act['id']}/submissions", files=[("files", ("p.png", png(), "image/png"))]).json()[0]["id"]
    get_store().update("submissions", sid, {"status": "grading", "grading_attempt": "test"})  # what jobs.start does
    jobs.grade_submission(get_store(), sid)
    return client.get(f"/api/submissions/{sid}").json()


@pytest.mark.parametrize(
    "rubric,total",
    [
        ([("Method", 4), ("Answer", 6)], 10),  # 2 criteria
        ([("Setup", 2), ("Method", 3), ("Computation", 3), ("Final answer", 2)], 10),  # 4 criteria
        ([("Given", 2), ("Formula", 2), ("Substitution", 2), ("Computation", 2), ("Answer", 2)], 10),  # 5 criteria
        ([("A", 1), ("B", 2), ("C", 3), ("D", 4)], 10),  # uneven
        ([("Setup", 5), ("Method", 8), ("Answer", 7)], 20),  # a different total
        ([("Idea", 1.5), ("Answer", 3.5)], 5),
    ],
)
def test_review_breakdown_matches_the_rubric_exactly(client, ai, rubric, total):
    r = make_activity(client, rubric, total, n_problems=2)
    assert r.status_code == 201, r.text
    act = r.json()
    assert act["rubric_total"] == total and act["rubric_errors"] == [] and act["total_points"] == total * 2
    # The AI awards half of each criterion but claims a wrong max (+1) for every unit; the rubric max must win.
    plan = {n: (p / 2, p + 1) for n, p in rubric}
    d = grade_one(client, ai, act, [plan])
    for prob in d["ai_result"]["problems"]:
        crit = prob["criteria_scores"]
        assert [(c["name"], c["points"]) for c in crit] == list(rubric)  # every criterion, exact max, rubric order
        assert sum(c["points"] for c in crit) == prob["max_score"] == total
        assert all(0 <= c["awarded"] <= c["points"] for c in crit)
        assert prob["final_score"] == round(sum(c["awarded"] for c in crit), 2) == total / 2
        assert all(u["points_max"] == dict(rubric)[u["criterion"]] for u in prob["units"])


def test_teacher_edit_updates_total_and_flows_to_gradebook_and_summary(client, ai):
    rubric = [("Setup", 2), ("Method", 3), ("Computation", 3), ("Final answer", 2)]
    act = make_activity(client, rubric, 10).json()
    d = grade_one(client, ai, act, [{"Setup": (2, 2), "Method": (1, 3), "Computation": (3, 3), "Final answer": (0, 2)}])
    sid, pid = d["id"], act["problems"][0]["id"]
    assert d["ai_result"]["problems"][0]["final_score"] == 6
    r = client.patch(f"/api/submissions/{sid}/review", json={"criterion_scores": {f"{pid}::Method": 3, f"{pid}::Final answer": 1.5}})
    p = r.json()["ai_result"]["problems"][0]
    assert p["final_score"] == 9.5 == sum(c["awarded"] for c in p["criteria_scores"])
    assert {c["name"]: c["edited"] for c in p["criteria_scores"]} == {"Setup": False, "Method": True, "Computation": False, "Final answer": True}
    assert client.patch(f"/api/submissions/{sid}/review", json={"criterion_scores": {f"{pid}::Setup": 2.5}}).status_code == 409
    assert client.patch(f"/api/submissions/{sid}/review", json={"criterion_scores": {f"{pid}::Setup": -1}}).status_code == 409
    # Clearing an edit goes back to the AI's points.
    p = client.patch(f"/api/submissions/{sid}/review", json={"criterion_scores": {f"{pid}::Final answer": None}}).json()["ai_result"]["problems"][0]
    assert p["final_score"] == 8
    a = client.post(f"/api/submissions/{sid}/approve").json()
    assert a["submission"]["status"] == "approved" and a["final_score"] == 8 == a["submission"]["review"]["final_score"]
    g = client.get(f"/api/activities/{act['id']}/gradebook").json()
    row = next(x for x in g["rows"] if x["submission_id"] == sid)
    assert row["scores"] == [8] and row["total"] == 8 and row["edited"] == [True]
    s = client.get(f"/api/activities/{act['id']}/class-summary").json()
    assert s["per_problem"][0]["average"] == 8 and s["out_of"] == 10 and "ai_model" not in s


def test_skipped_criterion_is_retried_then_left_at_zero_for_the_teacher(client, ai):
    rubric = [("Setup", 2), ("Method", 3), ("Computation", 3), ("Final answer", 2)]
    act = make_activity(client, rubric, 10).json()
    partial = {"Setup": (2, 2), "Method": (3, 3), "Final answer": (2, 2)}  # Computation never assessed
    full = {**partial, "Computation": (3, 3)}
    d = grade_one(client, ai, act, [partial, full])
    assert ai["calls"] == 2 and d["ai_result"]["problems"][0]["final_score"] == 10  # the retry fixed it
    d = grade_one(client, ai, act, [partial, partial])
    p = d["ai_result"]["problems"][0]
    comp = next(c for c in p["criteria_scores"] if c["name"] == "Computation")
    assert comp["awarded"] == 0 and comp["points"] == 3  # never invented
    assert p["final_score"] == 7 and p["max_score"] == 10
    assert d["status"] == "needs_review"  # the teacher has to score it


@pytest.mark.parametrize(
    "rubric,total,needle",
    [
        ([("Setup", 2), ("Method", 3), ("Answer", 3)], 10, "add up to 8 points, but the rubric total is 10"),
        ([("Setup", 6), ("Answer", 6)], 10, "add up to 12 points"),
        ([("Setup", 5), ("Answer", 5)], None, "total points"),
        ([], 10, "no criteria"),
        ([("Setup", 5), ("setup", 5)], 10, "must be different"),
        ([("Setup", 10), ("Answer", 0)], 10, "more than 0"),
        ([("", 5), ("Answer", 5)], 10, "needs a name"),
    ],
)
def test_invalid_rubrics_are_refused_with_a_clear_reason(client, rubric, total, needle):
    r = make_activity(client, rubric, total)
    assert r.status_code == 409 and needle in r.json()["detail"]
    assert rubric_problems([{"name": n, "points": p} for n, p in rubric], total)


def test_rubric_can_change_until_grading_then_is_locked(client, ai):
    act = make_activity(client, [("Method", 5), ("Answer", 5)], 10).json()
    bad = client.patch(f"/api/activities/{act['id']}/rubric", json={"criteria": [{"name": "Method", "points": 5}], "total_points": 10})
    assert bad.status_code == 409 and "add up to 5" in bad.json()["detail"]
    new = [{"name": "Setup", "description": "", "points": 1}, {"name": "Method", "description": "", "points": 2},
           {"name": "Work", "description": "", "points": 3}, {"name": "Answer", "description": "", "points": 4}]
    up = client.patch(f"/api/activities/{act['id']}/rubric", json={"criteria": new, "total_points": 10}).json()
    assert [c["name"] for c in up["rubric"]] == ["Setup", "Method", "Work", "Answer"] and not up["rubric_locked"]
    d = grade_one(client, ai, up, [{"Setup": (1, 1), "Method": (2, 2), "Work": (3, 3), "Answer": (0, 4)}])
    assert [(c["name"], c["points"]) for c in d["ai_result"]["problems"][0]["criteria_scores"]] == [("Setup", 1), ("Method", 2), ("Work", 3), ("Answer", 4)]
    assert d["ai_result"]["problems"][0]["final_score"] == 6
    assert client.get(f"/api/activities/{act['id']}").json()["rubric_locked"]
    locked = client.patch(f"/api/activities/{act['id']}/rubric", json={"criteria": new, "total_points": 10})
    assert locked.status_code == 409 and "already has graded papers" in locked.json()["detail"]


def test_grading_refuses_a_rubric_that_does_not_add_up(client):
    from app.store import get_store

    act = make_activity(client, [("Method", 5), ("Answer", 5)], 10).json()
    get_store().update("rubrics", f"{act['id']}-rubric", {"total_points": 12})  # e.g. an old row edited by hand
    client.post(f"/api/activities/{act['id']}/submissions", files=[("files", ("p.png", png(), "image/png"))])
    r = client.post(f"/api/activities/{act['id']}/grade")
    assert r.status_code == 409 and "Fix the rubric before grading" in r.json()["detail"]


TECH = ("claude", "haiku", "anthropic", "prompt_version", "model", "v1.1", "v1.2", "api key", "sdk")


def test_teacher_endpoints_expose_no_technical_details(client, ai):
    act = make_activity(client, [("Method", 5), ("Answer", 5)], 10).json()
    d = grade_one(client, ai, act, [{"Method": (5, 5), "Answer": (5, 5)}])
    pages = [
        client.get("/api/dashboard"), client.get(f"/api/activities/{A}"), client.get(f"/api/activities/{A}/queue"),
        client.get(f"/api/submissions/{d['id']}"), client.get(f"/api/activities/{A}/gradebook"),
        client.get(f"/api/activities/{A}/class-summary"), client.get("/api/notifications"), client.get("/api/profile"),
        client.get("/api/settings"),
    ]
    for r in pages:
        text = r.text.lower()
        for t in TECH:
            assert t not in text, f"{r.url} exposes {t!r}"


def test_legacy_problem_override_is_kept_as_criterion_scores(client):
    from app.store import get_store

    sid = "sub-math-2026-009"
    d = client.get(f"/api/submissions/{sid}").json()
    p = d["ai_result"]["problems"][0]
    target = p["max_score"] - 1 if p["final_score"] != p["max_score"] - 1 else p["max_score"]
    store = get_store()
    rev = store.one("teacher_reviews", submission_id=sid)
    store.update("teacher_reviews", rev["id"], {"problem_scores": {p["problem_id"]: target}, "criterion_scores": {}})
    p = client.get(f"/api/submissions/{sid}").json()["ai_result"]["problems"][0]
    assert p["final_score"] == target == sum(c["awarded"] for c in p["criteria_scores"])
    assert all(0 <= c["awarded"] <= c["points"] for c in p["criteria_scores"])
    after = client.patch(f"/api/submissions/{sid}/review", json={"feedback": {p["problem_id"]: "ok"}}).json()
    assert after["ai_result"]["problems"][0]["final_score"] == target
    assert not store.one("teacher_reviews", submission_id=sid).get("problem_scores")
