"""Token savings: usage tracking, smaller photos, the trimmed v1.3 output, and Saver grading (Batch API)."""
import io
import json
import time
from types import SimpleNamespace as NS

import pytest
from fastapi.testclient import TestClient

from tests.helpers import blank, sign_in
from PIL import Image

from app.config import get_settings
from app.grading import grader, images, llm
from app.services import batches

A = "act-linear-eq-quiz1"
RUBRIC = [("Setup", 2), ("Method", 3), ("Computation", 3), ("Final answer", 2)]


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
def live(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "demo_mode", False)
    monkeypatch.setattr(s, "anthropic_api_key", "sk-ant-test")
    return s


def v13_reply(problems, awarded=None):
    """A reply in the v1.3 shape: no expected_answer, points_max, suggested_score or max_score."""
    probs = []
    for p in problems:
        units = [
            {"index": i + 1, "transcribed_text": "x", "alt_reading": None, "verdict": "correct", "error_type": None, "criterion": c,
             "points_awarded": awarded if awarded is not None else pts, "confidence": 0.95, "comment": "", "bbox": None}
            for i, (c, pts) in enumerate(RUBRIC)
        ]
        probs.append({"problem_id": p["id"], "units": units, "overall_confidence": 0.95, "flags": [], "student_hint": "Good."})
    return json.dumps({"student_name": None, "student_id": None, "identity_confidence": 0, "problems": probs}, separators=(",", ":"))


def message(text, inp=1000, out=400, stop="end_turn"):
    return NS(content=[NS(type="text", text=text)], stop_reason=stop, usage=NS(input_tokens=inp, output_tokens=out))


def png(size, fmt="PNG", exif=None):
    buf = io.BytesIO()
    kw = {"exif": exif} if exif is not None else {}
    blank(size).save(buf, format=fmt, **kw)
    return buf.getvalue()


def wait_idle(client, activity_id):
    for _ in range(100):
        p = client.get(f"/api/activities/{activity_id}/grading-progress").json()
        if not any(i["state"] == "checking" for i in p["items"]) and (not p["running"] or p["saver"]):
            return p
        time.sleep(0.05)
    raise AssertionError("grading did not settle")


# ---------- usage tracking ----------


def test_call_records_token_usage(live, monkeypatch):
    calls = []

    class Messages:
        def create(self, **kw):
            calls.append(kw)
            return message("{}", inp=1200, out=300)

    monkeypatch.setattr(llm, "_client", lambda: NS(messages=Messages()))
    usage: dict = {}
    llm.call([{"role": "user", "content": "hi"}], usage=usage)
    llm.call([{"role": "user", "content": "hi"}], usage=usage)
    assert usage == {"input_tokens": 2400, "output_tokens": 600, "calls": 2}
    assert calls[0]["model"] == live.anthropic_model


def test_batch_tokens_are_counted_apart():
    usage: dict = {}
    llm.add_usage(usage, NS(input_tokens=100, output_tokens=50))
    llm.add_usage(usage, NS(input_tokens=100, output_tokens=50), batch=True)
    assert usage == {"input_tokens": 100, "output_tokens": 50, "batch_input_tokens": 100, "batch_output_tokens": 50, "calls": 2}


# ---------- smaller photos ----------


def test_large_photo_is_shrunk_to_what_the_model_reads():
    data, mt = images.prepare(png((4000, 3000), "JPEG"), "image/jpeg")
    img = Image.open(io.BytesIO(data))
    assert mt == "image/jpeg" and max(img.size) == images.MAX_EDGE and img.size == (1568, 1176)


def test_small_upright_photo_and_pdf_are_sent_unchanged():
    small = png((800, 1000))
    assert images.prepare(small, "image/png") == (small, "image/png")
    assert images.prepare(b"%PDF-1.4 ...", "application/pdf") == (b"%PDF-1.4 ...", "application/pdf")


def test_rotated_phone_photo_is_sent_upright():
    exif = Image.Exif()
    exif[0x0112] = 6  # stored sideways; shown rotated 90 degrees
    data, _ = images.prepare(png((1000, 600), "JPEG", exif=exif), "image/jpeg")
    assert Image.open(io.BytesIO(data)).size == (600, 1000)


def test_unreadable_photo_is_sent_as_is():
    assert images.prepare(b"not an image", "image/png") == (b"not an image", "image/png")


# ---------- trimmed output (prompt v1.3) ----------


def test_prompt_no_longer_asks_for_totals():
    text = grader.PROMPT_FILE.read_text()
    assert grader.PROMPT_VERSION == "v1.3"
    for field in ('"points_max"', '"suggested_score"', '"max_score"', '"expected_answer"'):
        assert field not in text
    assert "compactly" in text


def test_v13_reply_is_scored_from_the_rubric(client, live, monkeypatch):
    problems = client.get(f"/api/activities/{A}").json()["problems"]
    act = client.get(f"/api/activities/{A}").json()
    rubric = [{"name": c, "points": p, "description": ""} for c, p in RUBRIC]
    probs = [{"id": p["id"], "position": p["order"], "text": p["text"], "expected_answer": p["expected_answer"]} for p in problems]
    monkeypatch.setattr(llm, "call", lambda messages, max_tokens=16000, system=None, usage=None: (llm.add_usage(usage, NS(input_tokens=900, output_tokens=200)), v13_reply(probs, awarded=1))[1])
    r = grader.grade_image(png((400, 500)), "image/png", {"title": act["title"], "subject": "math", "settings": {}}, probs, rubric)
    assert r["status"] != "failed"
    p0 = r["problem_results"][0]
    assert p0["expected_answer"] == problems[0]["expected_answer"]  # from the answer key
    assert p0["max_score"] == 10 and p0["suggested_score"] == 4  # 1 point on each of 4 criteria
    assert [u["points_max"] for u in p0["units"]] == [2, 3, 3, 2]
    assert r["usage"] == {"input_tokens": 900, "output_tokens": 200, "calls": 1}


# ---------- Saver grading (Batch API) ----------


class FakeBatches:
    def __init__(self):
        self.created, self.status, self.counts, self.replies = [], "in_progress", (0, 0), {}

    def create(self, requests):
        self.created.append(requests)
        return NS(id=f"msgbatch_{len(self.created)}")

    def retrieve(self, batch_id):
        return NS(processing_status=self.status, request_counts=NS(succeeded=self.counts[0], errored=self.counts[1], canceled=0, expired=0))

    def results(self, batch_id):
        return [NS(custom_id=cid, result=r) for cid, r in self.replies.items()]


def test_saver_mode_grades_a_class_set_through_a_batch(client, live, monkeypatch):
    from app.store import get_store

    store = get_store()
    fake = FakeBatches()
    monkeypatch.setattr(llm, "_client", lambda: NS(messages=NS(batches=fake)))
    monkeypatch.setattr(batches, "ensure_poller", lambda store: None)  # the test drives polling itself
    live_calls = []
    problems = client.get(f"/api/activities/{A}").json()["problems"]
    probs = [{"id": p["id"]} for p in problems]

    def live_call(messages, max_tokens=16000, system=None, usage=None):
        live_calls.append(messages)
        llm.add_usage(usage, NS(input_tokens=2000, output_tokens=900))
        return v13_reply(probs)

    monkeypatch.setattr(llm, "call", live_call)
    assert client.patch("/api/settings", json={"grading_mode": "saver"}).json()["grading_mode"] == "saver"
    ids = []
    for _ in range(3):
        r = client.post(f"/api/activities/{A}/submissions", files=[("files", ("p.png", png((2400, 3200)), "image/png"))])
        ids.append(r.json()[0]["id"])

    client.post(f"/api/activities/{A}/grade")
    p = wait_idle(client, A)
    assert len(fake.created) == 1 and not live_calls  # nothing graded at full price
    reqs = fake.created[0]
    sent = batches.processing(store, A)[0]["requests"]
    assert set(ids) <= set(sent.values()) and len(reqs) == len(sent)
    img = reqs[0]["params"]["messages"][0]["content"][0]
    assert img["type"] == "image" and img["source"]["media_type"] == "image/jpeg"  # shrunk before upload
    assert reqs[0]["params"]["model"] == live.anthropic_model
    # While it runs, the teacher sees it's waiting and roughly how long is left
    assert p["running"] and p["saver"]["eta_basis"] == "typical" and 0 < p["saver"]["eta_seconds"] <= 3600
    assert p["saver"]["in_batch"] == len(sent) and p["saver"]["deadline"] > p["saver"]["submitted_at"]
    assert all(i["state"] == "waiting" for i in p["items"] if i["submission_id"] in ids)

    # The batch ends: one good reply, one that fails validation (retried live once), one errored (graded live)
    cids = {sid: cid for cid, sid in sent.items()}
    fake.replies = {cid: NS(type="succeeded", message=message(v13_reply(probs))) for cid in sent}
    fake.replies[cids[ids[1]]] = NS(type="succeeded", message=message("not json"))
    fake.replies[cids[ids[2]]] = NS(type="errored", error=NS(type="api_error"))
    fake.status, fake.counts = "ended", (len(sent) - 1, 1)
    batches.check(store, batches.processing(store, A)[0])

    assert not batches.processing(store, A)
    assert len(live_calls) == 2  # the retry for ids[1] and the errored ids[2]
    d0 = client.get(f"/api/submissions/{ids[0]}").json()
    assert d0["status"] in ("ready", "needs_review")
    usage = [r for r in store.select("ai_results", submission_id=ids[0])][-1]["usage"]
    assert usage == {"batch_input_tokens": 1000, "batch_output_tokens": 400, "calls": 1}
    retried = [r for r in store.select("ai_results", submission_id=ids[1])][-1]["usage"]
    assert retried["batch_output_tokens"] == 400 and retried["output_tokens"] == 900
    assert client.get(f"/api/submissions/{ids[2]}").json()["status"] in ("ready", "needs_review")
    notes = client.get("/api/notifications").json()["items"]
    assert any("Grading finished" in n["title"] for n in notes)
    p = client.get(f"/api/activities/{A}/grading-progress").json()
    assert not p["running"] and p["saver"] is None

    # Grade again on one paper is always graded right away, even in Saver mode
    before = len(fake.created)
    store.update("submissions", ids[0], {"status": "failed"})
    client.post(f"/api/submissions/{ids[0]}/regrade")
    wait_idle(client, A)
    assert len(fake.created) == before and len(live_calls) == 3
    client.patch("/api/settings", json={"grading_mode": "fast"})


def test_eta_uses_the_speed_so_far_then_past_batches(client, live):
    from app.store import get_store

    store = get_store()
    now = time.time()

    def iso(ago):
        from datetime import datetime, timezone

        return datetime.fromtimestamp(now - ago, timezone.utc).isoformat()

    act = "act-eta-test"
    store.delete("grading_batches", status="ended")  # only this test's batches count as history
    store.insert("grading_batches", {"id": "gb-eta", "activity_id": act, "provider_batch_id": "b", "requests": {"r0": "x"}, "status": "processing",
                                     "total": 100, "done": 25, "model": "m", "submitted_at": iso(600), "ended_at": None})
    e = batches.eta(store, act)
    assert e["eta_basis"] == "progress" and 1700 <= e["eta_seconds"] <= 1900  # 25% done in 10 min -> ~30 min left
    store.update("grading_batches", "gb-eta", {"done": 0})
    store.insert("grading_batches", {"id": "gb-old", "activity_id": "other", "provider_batch_id": "c", "requests": {}, "status": "ended",
                                     "total": 10, "done": 10, "model": "m", "submitted_at": iso(9000), "ended_at": iso(9000 - 1200)})
    e = batches.eta(store, act)
    assert e["eta_basis"] == "history" and 595 <= e["eta_seconds"] <= 600  # past batch took 20 min; 10 min already gone
    store.update("grading_batches", "gb-eta", {"submitted_at": iso(3000)})
    e = batches.eta(store, act)
    assert e["overdue"] and e["eta_seconds"] is None
    store.delete("grading_batches", id="gb-eta")
    store.delete("grading_batches", id="gb-old")
