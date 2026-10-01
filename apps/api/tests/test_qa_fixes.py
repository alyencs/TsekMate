"""Regression tests for the findings in docs/QA-AUDIT.md (see docs/QA-FIX-REPORT.md for the mapping)."""
from __future__ import annotations

import io
import json
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import get_settings
from app.grading import llm
from tests.helpers import TEACHER, blank, sign_in

A = "act-linear-eq-quiz1"


@pytest.fixture(scope="module")
def client():
    from app.main import app
    from app.seed import reset_and_seed
    from app.store import get_store

    with TestClient(app) as c:
        reset_and_seed(get_store())
        sign_in(c)
        yield c


@pytest.fixture
def anon():
    from app.main import app

    with TestClient(app) as c:
        yield c


def img_bytes(size=(400, 500), fmt="PNG") -> bytes:
    buf = io.BytesIO()
    blank(size).save(buf, format=fmt)
    return buf.getvalue()


_enrolled = [0]


def free_students(client, n=1) -> list[str]:
    """Enroll n new students in the activity's class (no paper yet)."""
    section = store().get("activities", A)["class_name"]
    out = []
    for _ in range(n):
        _enrolled[0] += 1
        sid = f"2026-9{_enrolled[0]:02d}"
        store().insert("students", {"id": sid, "name": f"Test Student {_enrolled[0]}", "section": section})
        out.append(sid)
    return out


def upload(client, student_id: str | None = None, data: bytes | None = None, name="p.png", ctype="image/png"):
    form = {"student_ids": student_id} if student_id else None
    return client.post(f"/api/activities/{A}/submissions", files=[("files", (name, img_bytes() if data is None else data, ctype))], data=form)


def store():
    from app.store import get_store

    return get_store()


def wait_idle(client, activity_id=A):
    for _ in range(300):
        if not client.get(f"/api/activities/{activity_id}/grading-progress").json()["running"]:
            return
        time.sleep(0.02)
    raise AssertionError("grading did not finish")


def paper_reply(problems, conf=0.95):
    from app.services.core import Bundle

    b = Bundle(store(), A)
    probs = []
    for p in problems:
        units = [{"index": i + 1, "transcribed_text": "x", "alt_reading": None, "verdict": "correct", "error_type": None, "criterion": c["name"],
                  "points_awarded": c["points"], "confidence": conf, "comment": "", "bbox": None} for i, c in enumerate(b.rubric)]
        probs.append({"problem_id": p["id"], "units": units, "overall_confidence": conf, "flags": [], "student_hint": ""})
    return json.dumps({"student_name": None, "student_id": None, "identity_confidence": 0, "problems": probs})


# ======================================================================== S-1 authentication
def all_routes():
    """Every (method, path) the app serves, including routes of included routers."""
    from app.main import app

    out = []

    def walk(routes):
        for r in routes:
            if hasattr(r, "methods") and hasattr(r, "path"):
                for m in r.methods - {"HEAD", "OPTIONS"}:
                    out.append((m, r.path))
            for attr in ("routes", "original_router"):
                sub = getattr(r, attr, None)
                if sub is not None:
                    walk(sub.routes if hasattr(sub, "routes") and not isinstance(sub, list) else sub)

    walk(app.routes)
    return sorted(set(out))


def test_every_route_except_the_public_ones_requires_sign_in(anon):
    from app.main import PUBLIC_ROUTES

    routes = [r for r in all_routes() if not r[1].startswith(("/docs", "/redoc", "/openapi"))]
    protected = [r for r in routes if r not in PUBLIC_ROUTES]
    assert len(protected) >= 40, protected  # the walk really found the included router
    for method, path in protected:
        url = path.replace("{path:path}", "x").replace("{activity_id}", A).replace("{sub_id}", "sub-math-2026-014").replace("{notification_id}", "n-1")
        for headers in ({}, {"Authorization": "Bearer nope"}, {"Authorization": "Basic YTpi"}, {"Authorization": "Bearer a.b"}):
            r = anon.request(method, url, headers=headers, json={})
            assert r.status_code == 401, (method, url, headers, r.status_code, r.text)
            assert r.json()["detail"] == "Please sign in to continue."


def test_unauthenticated_requests_cannot_read_or_change_anything(anon):
    for method, url, body in [
        ("GET", "/api/activities", None),
        ("GET", f"/api/activities/{A}/gradebook", None),
        ("GET", f"/api/activities/{A}/roster", None),
        ("GET", "/api/submissions/sub-math-2026-014", None),
        ("POST", f"/api/activities/{A}/grade", None),
        ("POST", "/api/submissions/sub-math-2026-014/regrade", None),
        ("POST", "/api/submissions/sub-math-2026-014/approve", None),
        ("DELETE", "/api/submissions/sub-math-2026-014", None),
        ("PATCH", "/api/settings", {"grading_mode": "saver"}),
        ("PATCH", "/api/profile", {"name": "Mallory"}),
        ("POST", "/adapter/grades/draft", {"activity_id": A}),
        ("GET", "/adapter/activities", None),
        ("GET", f"/adapter/submissions?activity_id={A}", None),
    ]:
        assert anon.request(method, url, json=body).status_code == 401, (method, url)
    # nothing changed
    assert store().get("submissions", "sub-math-2026-014")["status"] == "needs_review"
    from app.services import settings as app_settings

    assert app_settings.get(store())["grading_mode"] == "fast"
    assert app_settings.profile(store())["name"] != "Mallory"


def test_sign_in_issues_a_token_that_works_until_sign_out(anon):
    assert anon.post("/api/auth/signin", json={**TEACHER, "password": "wrong"}).status_code == 401
    r = anon.post("/api/auth/signin", json=TEACHER)
    assert r.status_code == 200 and r.json()["token"] and "password" not in r.text
    h = {"Authorization": f"Bearer {r.json()['token']}"}
    assert anon.get("/api/auth/me", headers=h).json()["email"] == TEACHER["email"]
    assert anon.get("/api/activities", headers=h).status_code == 200
    assert anon.post("/api/auth/signout", headers=h).status_code == 204
    assert anon.get("/api/activities", headers=h).status_code == 401  # revoked on the server, not just in the browser


def test_tampered_expired_and_old_password_tokens_are_refused(anon, monkeypatch):
    from app import auth

    token, _ = auth.issue_token()
    payload, sig = token.split(".")
    assert auth.read_token(token)
    assert auth.read_token(payload + "." + sig[:-2] + ("AA" if not sig.endswith("AA") else "BB")) is None  # signature
    forged = json.loads(auth._unb64(payload))
    forged["exp"] += 10**6
    assert auth.read_token(auth._b64(json.dumps(forged).encode()) + "." + sig) is None  # payload changed
    old, _ = auth.issue_token(now=time.time() - 3 * 24 * 3600)
    assert auth.read_token(old) is None  # expired
    monkeypatch.setattr(get_settings(), "teacher_password", "a-new-password")
    assert auth.read_token(token) is None  # password changed: every earlier session ends
    monkeypatch.setattr(get_settings(), "teacher_password", TEACHER["password"])
    monkeypatch.setattr(get_settings(), "teacher_email", "someone@else.edu")
    assert auth.read_token(token) is None


def test_sign_in_is_throttled_after_repeated_failures(anon):
    from app import auth

    auth._failures.clear()
    for _ in range(auth.MAX_FAILURES):
        assert anon.post("/api/auth/signin", json={**TEACHER, "password": "nope"}).status_code == 401
    assert anon.post("/api/auth/signin", json=TEACHER).status_code == 429  # even the right password waits
    auth._failures.clear()
    assert anon.post("/api/auth/signin", json=TEACHER).status_code == 200


def test_image_links_need_a_valid_signature(client, anon):
    url = client.get("/api/submissions/sub-math-2026-014").json()["image_url"]
    path = url.split("/api/images/")[1]
    assert anon.get("/api/images/" + path).status_code == 200  # an <img> cannot send headers; the signature is the key
    assert anon.get("/api/images/" + path.replace("sig=", "sig=0")).status_code in (403, 422)
    assert anon.get("/api/images/seed/sub-math-2026-014.jpg").status_code == 422  # no signature at all


# ======================================================================== S-2 secrets / production config
def test_production_refuses_missing_or_default_secrets(monkeypatch):
    from app.config import ConfigError, Settings

    monkeypatch.setenv("APP_ENV", "production")
    for k in ("AUTH_SECRET", "IMAGE_SIGNING_SECRET", "DEMO_TEACHER_PASSWORD"):
        monkeypatch.setenv(k, "")
    with pytest.raises(ConfigError) as e:
        Settings()
    assert "AUTH_SECRET" in str(e.value) and "IMAGE_SIGNING_SECRET" in str(e.value) and "DEMO_TEACHER_PASSWORD" in str(e.value)
    monkeypatch.setenv("AUTH_SECRET", "change-me")
    monkeypatch.setenv("IMAGE_SIGNING_SECRET", "local-dev-only-secret")
    monkeypatch.setenv("DEMO_TEACHER_PASSWORD", "tsekmate")
    with pytest.raises(ConfigError):
        Settings()
    monkeypatch.setenv("AUTH_SECRET", "a" * 40)
    monkeypatch.setenv("IMAGE_SIGNING_SECRET", "b" * 40)
    monkeypatch.setenv("DEMO_TEACHER_PASSWORD", "a-long-teacher-password")
    s = Settings()
    assert s.is_production and not s.security_problems()


def test_development_never_uses_a_known_secret(monkeypatch):
    from app.config import KNOWN_PLACEHOLDERS, Settings

    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AUTH_SECRET", "change-me")
    monkeypatch.setenv("IMAGE_SIGNING_SECRET", "")
    a, b = Settings(), Settings()
    assert a.auth_secret not in KNOWN_PLACEHOLDERS and len(a.auth_secret) >= 32 and a.auth_secret != b.auth_secret
    assert a.signing_secret not in KNOWN_PLACEHOLDERS and len(a.signing_secret) >= 32


# ======================================================================== S-4 health
def test_public_health_discloses_nothing(anon, client):
    assert anon.get("/api/health").json() == {"ok": True}
    assert anon.get("/api/admin/health").status_code == 401
    assert "model" in client.get("/api/admin/health").json()


# ======================================================================== S-5 / B-4 uploads
def test_fake_and_damaged_uploads_are_rejected(client):
    before = len(store().select("submissions", activity_id=A))
    for name, data, ctype in [
        ("a.jpg", b"<html><script>alert(1)</script></html>", "image/jpeg"),
        ("b.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 64, "image/png"),  # PNG signature, garbage inside
        ("c.jpg", b"\xff\xd8\xff" + b"junk" * 50, "image/jpeg"),
        ("d.pdf", b"%PDF-1.4 not really a pdf", "application/pdf"),  # no end marker
        ("e.gif", b"GIF89a" + b"\x00" * 40, "image/gif"),
        ("f.txt", b"hello", "text/plain"),
    ]:
        r = upload(client, data=data, name=name, ctype=ctype)
        assert r.status_code == 415, (name, r.status_code, r.text)
    assert upload(client, data=b"", name="empty.png").status_code == 400
    assert len(store().select("submissions", activity_id=A)) == before


def test_oversized_and_too_many_uploads_are_rejected(client, monkeypatch):
    from app.services import uploads

    monkeypatch.setattr(uploads, "MAX_PIXELS", 1000)
    assert upload(client).status_code == 413  # 400 x 500 > 1000 pixels: refused before decoding
    monkeypatch.setattr(uploads, "MAX_PIXELS", 40_000_000)
    monkeypatch.setattr(uploads, "MAX_FILES", 2)
    r = client.post(f"/api/activities/{A}/submissions", files=[("files", (f"{i}.png", img_bytes(), "image/png")) for i in range(3)])
    assert r.status_code == 413


@pytest.mark.parametrize("fmt,ctype,ext", [("JPEG", "image/jpeg", "jpg"), ("PNG", "image/png", "png"), ("WEBP", "image/webp", "webp")])
def test_real_images_keep_their_type_whatever_the_browser_says(client, fmt, ctype, ext):
    r = upload(client, data=img_bytes(fmt=fmt), name=f"p.{ext}", ctype="application/octet-stream")
    assert r.status_code == 201, r.text
    sub = store().get("submissions", r.json()[0]["id"])
    assert sub["image_path"].endswith("." + ext)
    data, stored_type = store().get_image(sub["image_path"])
    assert stored_type == ctype and data[:4] == img_bytes(fmt=fmt)[:4]
    url = r.json()[0]["image_url"]
    got = TestClient(client.app).get(url.split("http://localhost:8000")[1])
    assert got.status_code == 200 and got.headers["content-type"] == ctype and got.headers["x-content-type-options"] == "nosniff"
    client.delete(f"/api/submissions/{sub['id']}")


def tiny_pdf() -> bytes:
    buf = io.BytesIO()
    blank((200, 260)).save(buf, format="PDF")
    return buf.getvalue()


def test_pdf_is_stored_and_graded_as_a_document(client, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "anthropic_api_key", "sk-ant-test")
    monkeypatch.setattr(s, "demo_mode", False)
    sent = {}

    def fake_call(messages, max_tokens=16000, system=None, usage=None):
        sent["block"] = messages[0]["content"][0]
        from app.services.core import Bundle

        return paper_reply(Bundle(store(), A).problems)

    monkeypatch.setattr(llm, "call", fake_call)
    r = upload(client, data=tiny_pdf(), name="scan.pdf", ctype="image/jpeg")  # browser label is wrong on purpose
    assert r.status_code == 201, r.text
    sid = r.json()[0]["id"]
    assert store().get_image(store().get("submissions", sid)["image_path"])[1] == "application/pdf"
    client.post(f"/api/submissions/{sid}/regrade")
    wait_idle(client)
    assert sent["block"]["mime_type"] == "application/pdf"
    claude = llm._to_claude([{"role": "user", "content": [sent["block"]]}])[0]["content"][0]
    assert claude["type"] == "document" and claude["source"]["media_type"] == "application/pdf"
    assert store().get("submissions", sid)["status"] in ("needs_review", "ready")
    client.delete(f"/api/submissions/{sid}")


def test_supabase_store_reads_files_back_with_their_real_type():
    from app.store.supabase_store import SupabaseStore

    fs = FakeSupabase()
    st = SupabaseStore("u", "k", "b", client=fs)
    for path, ct in [("uploads/a/s1.pdf", "application/pdf"), ("uploads/a/s2.webp", "image/webp"), ("uploads/a/s3.png", "image/png"),
                     ("uploads/a/s4.jpg", "image/jpeg"), ("seed/s5.jpg", "image/jpeg")]:
        st.put_image(path, b"x", ct)
        assert st.get_image(path) == (b"x", ct)
        assert fs.files[path][1] == ct  # stored with that content type too


# ======================================================================== B-11 / B-22 Supabase store details
class FakeQuery:
    def __init__(self, db, table, op, payload=None):
        self.db, self.table, self.op, self.payload, self.filters = db, table, op, payload, []

    def eq(self, k, v):
        self.filters.append(("eq", k, v))
        return self

    def is_(self, k, v):
        self.filters.append(("is", k, v))
        return self

    def neq(self, k, v):
        self.filters.append(("neq", k, v))
        return self

    def in_(self, k, v):
        self.filters.append(("in", k, tuple(v)))
        return self

    def _match(self, row):
        for op, k, v in self.filters:
            if op == "eq" and row.get(k) != v or op == "is" and row.get(k) is not None or op == "neq" and row.get(k) == v or op == "in" and row.get(k) not in v:
                return False
        return True

    def execute(self):
        rows = self.db.tables.setdefault(self.table, {})
        self.db.log.append((self.table, self.op, list(self.filters)))
        if self.op == "select":
            data = [dict(r) for r in rows.values() if self._match(r)]
        elif self.op == "upsert":
            for r in self.payload:
                if self.db.unique_fail:
                    raise type("APIError", (Exception,), {"code": "23505", "message": "duplicate key"})()
                rows[r["id"]] = dict(r)
            data = list(self.payload)
        elif self.op == "update":
            data = []
            for r in rows.values():
                if self._match(r):
                    r.update(self.payload)
                    data.append(dict(r))
        else:
            data = [r for r in rows.values() if self._match(r)]
            for r in data:
                del rows[r["id"]]
        return type("Res", (), {"data": data})()


class FakeTable:
    def __init__(self, db, name):
        self.db, self.name = db, name

    def select(self, _cols):
        return FakeQuery(self.db, self.name, "select")

    def upsert(self, rows):
        return FakeQuery(self.db, self.name, "upsert", rows)

    def update(self, patch):
        return FakeQuery(self.db, self.name, "update", patch)

    def delete(self):
        return FakeQuery(self.db, self.name, "delete")


class FakeBucket:
    def __init__(self, db):
        self.db = db

    def upload(self, path, data, opts):
        self.db.files[path] = (data, opts["content-type"])

    def download(self, path):
        return self.db.files[path][0]

    def remove(self, paths):
        self.db.removes += 1
        for p in paths:
            self.db.files.pop(p, None)  # a folder path removes nothing, like Supabase Storage

    def list(self, folder, opts):
        names, out = set(), []
        for p in sorted(self.db.files):
            if not p.startswith(folder + "/"):
                continue
            rest = p[len(folder) + 1 :]
            head = rest.split("/")[0]
            if head in names:
                continue
            names.add(head)
            out.append({"name": head, "id": None if "/" in rest else "file-id"})
        return out[opts.get("offset", 0) : opts.get("offset", 0) + opts["limit"]]


class FakeSupabase:
    def __init__(self):
        self.tables, self.files, self.log, self.removes, self.unique_fail = {}, {}, [], 0, False
        self.storage = type("S", (), {"from_": lambda _s, _b: FakeBucket(self)})()

    def table(self, name):
        return FakeTable(self, name)


def test_supabase_reset_removes_nested_uploads_and_finishes():
    from app.store.supabase_store import SupabaseStore

    fs = FakeSupabase()
    st = SupabaseStore("u", "k", "b", client=fs)
    for i in range(3):
        st.put_image(f"uploads/act-{i}/sub-{i}.jpg", b"x", "image/jpeg")
        st.put_image(f"seed/sub-{i}.jpg", b"x", "image/jpeg")
    done = threading.Event()
    t = threading.Thread(target=lambda: (st.reset(), done.set()), daemon=True)
    t.start()
    assert done.wait(5), "reset() did not finish"
    assert fs.files == {}


def test_supabase_compare_and_set_none_filters_and_unique_violation():
    from app.store.base import UniqueViolation
    from app.store.supabase_store import SupabaseStore

    fs = FakeSupabase()
    st = SupabaseStore("u", "k", "b", client=fs)
    st.insert("submissions", {"id": "s1", "status": "grading", "grading_attempt": "a1", "student_id": None})
    assert st.update_where("submissions", "s1", {"status": "ready"}, status="grading", grading_attempt="old") is None
    assert st.get("submissions", "s1")["status"] == "grading"
    assert st.update_where("submissions", "s1", {"status": "ready"}, status="grading", grading_attempt="a1")["status"] == "ready"
    st.delete("submissions", student_id=None)  # None must mean IS NULL, as in select()
    assert ("submissions", "delete", [("is", "student_id", "null")]) in fs.log
    fs.unique_fail = True
    with pytest.raises(UniqueViolation):
        st.insert("submissions", {"id": "s2"})


# ======================================================================== B-1 stuck grading
def make_stuck(client, minutes_ago: float, with_result: bool) -> str:
    """A paper left in `grading` by a run that no longer exists."""
    from app.services import jobs

    sid = upload(client).json()[0]["id"]
    if with_result:  # a failed paper that was being graded again
        store().update("submissions", sid, {"status": "grading", "grading_attempt": "x0"})
        jobs.grade_submission(store(), sid)  # no API key in tests: a failed result
        assert store().get("submissions", sid)["status"] == "failed"
    ts = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()
    store().update("submissions", sid, {"status": "grading", "grading_attempt": "lost-run", "updated_at": ts})
    return sid


def test_paper_left_grading_by_a_previous_process_is_released(client, monkeypatch):
    from app.services import jobs

    monkeypatch.setattr(get_settings(), "anthropic_api_key", None)
    monkeypatch.setattr(jobs, "PROCESS_STARTED", datetime.now(timezone.utc))
    sid = make_stuck(client, minutes_ago=1, with_result=False)  # before this "process" started
    p = client.get(f"/api/activities/{A}/grading-progress").json()
    assert store().get("submissions", sid)["status"] == "uploaded" and p["running"] is False
    sid2 = make_stuck(client, minutes_ago=1, with_result=True)
    client.get(f"/api/activities/{A}/grading-progress")
    s2 = store().get("submissions", sid2)
    assert s2["status"] == "failed" and s2["grading_attempt"] is None
    assert "interrupted" in client.get(f"/api/submissions/{sid2}").json()["ai_result"]["failure_reason"]
    # recoverable: Grade again and delete both work, and Grade all picks it up again
    assert client.post(f"/api/submissions/{sid2}/regrade").status_code == 200
    wait_idle(client)
    assert store().get("submissions", sid2)["status"] == "failed"  # no key: graded and failed cleanly, not stuck
    assert client.delete(f"/api/submissions/{sid2}").status_code == 204
    assert client.delete(f"/api/submissions/{sid}").status_code == 204


def test_stale_paper_from_this_process_is_released_after_the_timeout(client, monkeypatch):
    from app.services import jobs

    monkeypatch.setattr(jobs, "PROCESS_STARTED", datetime.now(timezone.utc) - timedelta(hours=2))
    fresh = make_stuck(client, minutes_ago=5, with_result=False)  # maybe still running elsewhere: left alone
    old = make_stuck(client, minutes_ago=45, with_result=False)
    leftovers = [x["id"] for x in store().select("submissions", status="grading") if x["id"] not in (fresh, old)]
    assert set(jobs.recover_stale(store(), A)) == {old}, leftovers
    assert store().get("submissions", fresh)["status"] == "grading"
    p = client.get(f"/api/activities/{A}/grading-progress").json()
    assert p["running"] is True  # the page keeps waiting for the live one, it does not report it done
    assert set(jobs.recover_stale(store(), A, now=datetime.now(timezone.utc) + timedelta(hours=1))) == {fresh}
    p = client.get(f"/api/activities/{A}/grading-progress").json()
    assert p["running"] is False, (p, [x["id"] for x in store().select("submissions", status="grading")], fresh)
    for sid in (fresh, old):
        client.delete(f"/api/submissions/{sid}")


def test_paper_in_a_processing_batch_and_in_flight_papers_are_never_released(client, monkeypatch):
    from app.services import jobs

    monkeypatch.setattr(jobs, "PROCESS_STARTED", datetime.now(timezone.utc))
    in_batch = make_stuck(client, minutes_ago=600, with_result=False)
    store().insert("grading_batches", {"id": "gb-test", "activity_id": A, "provider_batch_id": "msgbatch_x", "requests": {"r0": in_batch},
                                       "status": "processing", "total": 1, "done": 0, "model": "m", "submitted_at": datetime.now(timezone.utc).isoformat(), "ended_at": None})
    flying = make_stuck(client, minutes_ago=600, with_result=False)
    jobs._inflight[flying] = "lost-run"
    try:
        assert jobs.recover_stale(store(), A) == []
    finally:
        jobs._inflight.pop(flying, None)
        store().delete("grading_batches", id="gb-test")
    assert set(jobs.recover_stale(store(), A)) == {in_batch, flying}  # released once nothing owns them
    for sid in (in_batch, flying):
        client.delete(f"/api/submissions/{sid}")


def test_crash_inside_a_grading_thread_marks_the_paper_failed(client, monkeypatch):
    from app.services import jobs

    sid = upload(client).json()[0]["id"]

    def boom(*_a, **_k):
        raise RuntimeError("database went away")

    monkeypatch.setattr(jobs, "grade_submission", boom)
    assert client.post(f"/api/submissions/{sid}/regrade").status_code == 200
    wait_idle(client)
    monkeypatch.undo()
    assert store().get("submissions", sid)["status"] == "failed"
    client.delete(f"/api/submissions/{sid}")


# ======================================================================== B-2 approve vs Grade again
@pytest.fixture
def slow_ai(monkeypatch):
    """A fake model that blocks until the test releases it."""
    s = get_settings()
    monkeypatch.setattr(s, "anthropic_api_key", "sk-ant-test")
    monkeypatch.setattr(s, "demo_mode", False)
    gate, entered = threading.Event(), threading.Event()

    def fake_call(messages, max_tokens=16000, system=None, usage=None):
        from app.services.core import Bundle

        entered.set()
        assert gate.wait(10)
        return paper_reply(Bundle(store(), A).problems)

    monkeypatch.setattr(llm, "call", fake_call)
    return gate, entered


def failed_paper_for_student(client, monkeypatch) -> str:
    from app.services import jobs

    st = free_students(client)[0]
    sid = upload(client, student_id=st).json()[0]["id"]
    store().update("submissions", sid, {"status": "grading", "grading_attempt": "first"})
    key = get_settings().anthropic_api_key
    monkeypatch.setattr(get_settings(), "anthropic_api_key", None)
    jobs.grade_submission(store(), sid)
    monkeypatch.setattr(get_settings(), "anthropic_api_key", key)
    assert store().get("submissions", sid)["status"] == "failed"
    return sid


def test_approve_is_refused_while_grade_again_runs_and_the_result_is_deterministic(client, monkeypatch, slow_ai):
    gate, entered = slow_ai
    sid = failed_paper_for_student(client, monkeypatch)
    assert client.post(f"/api/submissions/{sid}/regrade").status_code == 200
    assert entered.wait(5)
    # every teacher write to the paper is refused while it is being graded
    assert client.post(f"/api/submissions/{sid}/approve").status_code == 409
    assert client.patch(f"/api/submissions/{sid}/review", json={"feedback": {}}).status_code == 409
    assert client.patch(f"/api/submissions/{sid}/student", json={"student_id": free_students(client)[0]}).status_code == 409
    assert client.delete(f"/api/submissions/{sid}").status_code == 409
    gate.set()
    wait_idle(client)
    s = store().get("submissions", sid)
    assert s["status"] in ("ready", "needs_review") and s["grading_attempt"] is None
    assert client.post(f"/api/submissions/{sid}/approve").status_code == 200
    assert store().get("submissions", sid)["status"] == "approved"


def test_stale_grading_result_never_overwrites_a_newer_teacher_action(client, monkeypatch, slow_ai):
    """The old run is still in flight when the paper is released (for example by another instance) and the teacher
    grades it by hand and approves it. The old run's late result must be discarded."""
    gate, entered = slow_ai
    sid = failed_paper_for_student(client, monkeypatch)
    ai_before = len(store().select("ai_results", submission_id=sid))
    assert client.post(f"/api/submissions/{sid}/regrade").status_code == 200
    assert entered.wait(5)
    store().update("submissions", sid, {"status": "failed", "grading_attempt": None})  # released elsewhere
    pid = store().select("problems", activity_id=A)[0]["id"]
    assert client.patch(f"/api/submissions/{sid}/review", json={"criterion_scores": {f"{pid}::Setup": 2}}).status_code == 200
    assert client.post(f"/api/submissions/{sid}/approve").status_code == 200
    gate.set()
    wait_idle(client)
    s = store().get("submissions", sid)
    assert s["status"] == "approved"
    assert len(store().select("ai_results", submission_id=sid)) == ai_before  # the late result left no trace
    rev = store().one("teacher_reviews", submission_id=sid)
    assert rev["approved"] is True and rev["criterion_scores"] == {f"{pid}::Setup": 2.0}


def test_concurrent_approvals_and_grade_again_end_in_one_consistent_state(client, monkeypatch):
    sid = failed_paper_for_student(client, monkeypatch)
    pid = store().select("problems", activity_id=A)[0]["id"]
    client.patch(f"/api/submissions/{sid}/review", json={"criterion_scores": {f"{pid}::Setup": 1}})
    monkeypatch.setattr(get_settings(), "anthropic_api_key", None)
    results = []

    def act(kind):
        url = f"/api/submissions/{sid}/approve" if kind == "approve" else f"/api/submissions/{sid}/regrade"
        results.append((kind, client.post(url).status_code))

    threads = [threading.Thread(target=act, args=(k,)) for k in ("approve", "regrade", "approve", "regrade")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    wait_idle(client)
    s = store().get("submissions", sid)
    rev = store().one("teacher_reviews", submission_id=sid)
    if s["status"] == "approved":
        assert rev and rev["approved"] is True
    else:
        assert s["status"] == "failed" and (rev is None or rev["approved"] is False)
    assert all(code in (200, 409) for _k, code in results), results


# ======================================================================== B-3 / B-7 numbers
BAD_NUMBERS = ["NaN", "Infinity", "-Infinity"]


def raw(client, method, url, body: str):
    return client.request(method, url, content=body, headers={"content-type": "application/json"})


@pytest.mark.parametrize("bad", BAD_NUMBERS)
def test_non_finite_numbers_are_rejected_everywhere_and_never_stored(client, bad):
    acts_before = len(store().select("activities"))
    body = ('{"title":"t","subject":"math","class_name":"X","date":"2026-01-01","problems":[{"order":1,"text":"a","expected_answer":"b"}],'
            f'"rubric":[{{"name":"A","points":{bad}}}],"rubric_total":10}}')
    assert raw(client, "POST", "/api/activities", body).status_code == 422
    body = body.replace(f'"points":{bad}', '"points":10').replace('"rubric_total":10', f'"rubric_total":{bad}')
    assert raw(client, "POST", "/api/activities", body).status_code == 422
    assert len(store().select("activities")) == acts_before
    sid = "sub-math-2026-014"
    pid = store().get("submissions", sid) and store().select("problems", activity_id=A)[0]["id"]
    for payload in [f'{{"criterion_scores":{{"{pid}::Setup":{bad}}}}}', f'{{"unit_edits":{{"{pid}:1":{{"points_awarded":{bad}}}}}}}']:
        assert raw(client, "PATCH", f"/api/submissions/{sid}/review", payload).status_code == 422
    assert raw(client, "PATCH", f"/api/activities/{A}/rubric", f'{{"criteria":[{{"name":"A","points":{bad}}}],"total_points":5}}').status_code == 422
    assert raw(client, "PATCH", "/api/settings", f'{{"confidence_threshold":{bad}}}').status_code == 422
    assert raw(client, "POST", "/api/rubric/generate", f'{{"subject":"math","title":"x","points_per_problem":{bad}}}').status_code == 422
    # nothing was stored, and every page still works
    rev = store().one("teacher_reviews", submission_id=sid) or {}
    assert "nan" not in json.dumps(rev.get("edit_log") or []).lower() and "infinity" not in json.dumps(rev).lower()
    for url in ("/api/activities", "/api/dashboard", f"/api/submissions/{sid}", f"/api/activities/{A}/gradebook", f"/api/activities/{A}/class-summary"):
        assert client.get(url).status_code == 200, url


def test_invalid_unit_edit_types_are_422_and_valid_edits_still_work(client):
    sid = "sub-math-2026-014"
    d = client.get(f"/api/submissions/{sid}").json()
    p = d["ai_result"]["problems"][0]
    key = f"{p['problem_id']}:{p['units'][0]['index']}"
    for edit in [{"points_awarded": None}, {"points_awarded": "x"}, {"points_awarded": -1}, {"points_awarded": []},
                 {"comment": None}, {"comment": 5}, {"transcribed_text": None}, {"verdict": "maybe"}, {"unknown": 1}]:
        r = client.patch(f"/api/submissions/{sid}/review", json={"unit_edits": {key: edit}})
        assert r.status_code == 422, (edit, r.status_code, r.text)
    assert client.patch(f"/api/submissions/{sid}/review", json={"criterion_scores": {f"{p['problem_id']}::Setup": "x"}}).status_code == 422
    assert client.patch(f"/api/submissions/{sid}/review", json={"criterion_scores": {f"{p['problem_id']}::Setup": 99}}).status_code == 409
    r = client.patch(f"/api/submissions/{sid}/review", json={"unit_edits": {key: {"points_awarded": 1.5, "comment": "ok", "error_type": None}}})
    assert r.status_code == 200
    assert client.get(f"/api/activities/{A}/class-summary").status_code == 200


def test_activity_date_must_be_a_real_date(client):
    body = {"title": "t", "subject": "math", "class_name": "X", "date": "yesterday", "problems": [{"order": 1, "text": "a", "expected_answer": "b"}],
            "rubric": [{"name": "A", "points": 10}], "rubric_total": 10}
    assert client.post("/api/activities", json=body).status_code == 422


# ======================================================================== B-5 duplicates
def test_one_student_can_not_get_two_papers(client):
    a, b = free_students(client, 2)
    r = client.post(f"/api/activities/{A}/submissions", files=[("files", ("1.png", img_bytes(), "image/png")), ("files", ("2.png", img_bytes(), "image/png"))],
                    data={"student_ids": f"{a},{a}"})
    assert r.status_code == 409 and "more than one file" in r.json()["detail"]
    assert [s for s in store().select("submissions", activity_id=A) if s.get("student_id") == a] == []
    first = upload(client, student_id=a)
    assert first.status_code == 201
    assert upload(client, student_id=a).status_code == 409  # a repeated request
    other = upload(client).json()[0]["id"]  # unidentified paper stays unidentified
    assert store().get("submissions", other)["student_id"] is None
    assert client.patch(f"/api/submissions/{other}/student", json={"student_id": a}).status_code == 409
    assert client.patch(f"/api/submissions/{other}/student", json={"student_id": b}).status_code == 200  # legitimate
    for sid in (first.json()[0]["id"], other):
        client.delete(f"/api/submissions/{sid}")


def test_the_same_photo_can_not_be_uploaded_twice(client):
    data = img_bytes()
    first = upload(client, data=data)
    assert first.status_code == 201
    assert upload(client, data=data).status_code == 409
    r = client.post(f"/api/activities/{A}/submissions", files=[("files", ("x.png", (d := img_bytes()), "image/png")), ("files", ("y.png", d, "image/png"))])
    assert r.status_code == 409
    client.delete(f"/api/submissions/{first.json()[0]['id']}")
    assert upload(client, data=data).status_code == 201  # a retake after deleting is fine


def test_concurrent_assignments_give_the_student_to_exactly_one_paper(client):
    st = free_students(client)[0]
    papers = [upload(client).json()[0]["id"] for _ in range(6)]
    codes = []
    threads = [threading.Thread(target=lambda sid=sid: codes.append(client.patch(f"/api/submissions/{sid}/student", json={"student_id": st}).status_code)) for sid in papers]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(codes) == [200] + [409] * 5
    assert len([s for s in store().select("submissions", activity_id=A) if s.get("student_id") == st]) == 1
    for sid in papers:
        client.delete(f"/api/submissions/{sid}")


def test_store_itself_refuses_a_second_paper_for_a_student():
    from app.store.base import UniqueViolation
    from app.store.memory import MemoryStore

    m = MemoryStore("http://x", "k")
    m.insert("submissions", {"id": "a", "activity_id": "x", "student_id": "s1"})
    m.insert("submissions", {"id": "b", "activity_id": "x", "student_id": None})
    m.insert("submissions", {"id": "c", "activity_id": "x", "student_id": None})  # many unidentified papers are fine
    m.insert("submissions", {"id": "d", "activity_id": "y", "student_id": "s1"})  # same student, other activity
    with pytest.raises(UniqueViolation):
        m.insert("submissions", {"id": "e", "activity_id": "x", "student_id": "s1"})
    with pytest.raises(UniqueViolation):
        m.update("submissions", "b", {"student_id": "s1"})


# ======================================================================== B-6 approved papers
def test_editing_an_approved_paper_withdraws_the_approval_until_approved_again(client):
    sid = next(s["id"] for s in store().select("submissions", activity_id=A) if s["status"] == "approved")
    st = store().get("submissions", sid)["student_id"]
    book = lambda: next(r for r in client.get(f"/api/activities/{A}/gradebook").json()["rows"] if r["student_id"] == st)  # noqa: E731
    before = book()
    assert before["total"] is not None
    # a save that changes nothing keeps the approval
    assert client.patch(f"/api/submissions/{sid}/review", json={"feedback": {}}).json()["status"] == "approved"
    pid = store().select("problems", activity_id=A)[0]["id"]
    d = client.patch(f"/api/submissions/{sid}/review", json={"criterion_scores": {f"{pid}::Setup": 0}}).json()
    assert d["status"] in ("ready", "needs_review") and d["review"]["approved"] is False
    assert book()["total"] is None  # the gradebook never shows an unapproved change
    assert all(g["student_ref"] != st for g in client.post("/adapter/grades/draft", json={"activity_id": A}).json()["grades"])
    assert client.post(f"/api/submissions/{sid}/approve").status_code == 200
    after = book()
    assert after["total"] is not None and after["status"] == "Approved"
    log = store().one("teacher_reviews", submission_id=sid)["edit_log"]
    assert [e["to"] for e in log if e["field"] == "approved"][-2:] == [False, True]


# ======================================================================== B-16 parent messages / adapter
def test_parent_message_rules(client, monkeypatch):
    unapproved = "sub-math-2026-014"
    assert client.post(f"/api/submissions/{unapproved}/parent-message/approve", json={"language": "en", "text": "hi"}).status_code == 409
    assert client.get(f"/api/submissions/{unapproved}/parent-message").status_code == 409
    approved = next(s["id"] for s in store().select("submissions", activity_id=A) if s["status"] == "approved")

    def no_ai(*_a, **_k):
        raise AssertionError("opening the parent page must not call the AI")

    monkeypatch.setattr(llm, "call", no_ai)
    r = client.get(f"/api/submissions/{approved}/parent-message")
    assert r.status_code == 200 and r.json()["drafted"] is False
    assert client.post(f"/api/submissions/{approved}/parent-message/approve", json={"language": "fil", "text": "Salamat po"}).status_code == 200
    assert client.get(f"/api/submissions/{approved}/parent-message").json()["last_approved_at"]


def test_adapter_export_needs_the_teacher_session(client, anon):
    assert anon.post("/adapter/grades/draft", json={"activity_id": A}).status_code == 401
    r = client.post("/adapter/grades/draft", json={"activity_id": A})
    assert r.status_code == 200 and r.json()["accepted"] >= 1
    assert client.post("/adapter/grades/draft", json={}).status_code == 422


# ======================================================================== B-14 class summary
def test_opening_the_class_summary_never_calls_the_ai(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "sk-ant-test")
    calls = []

    def fake_call(messages, max_tokens=16000, system=None, usage=None):
        calls.append(1)
        return json.dumps({"misconceptions": [], "reteach_focus": "Practice distributing a negative sign."})

    monkeypatch.setattr(llm, "call", fake_call)
    pid = store().select("problems", activity_id=A)[1]["id"]
    sid = "sub-math-2026-014"
    d = client.get(f"/api/submissions/{sid}").json()
    u = next(p for p in d["ai_result"]["problems"] if p["problem_id"] == pid)["units"][0]
    client.patch(f"/api/submissions/{sid}/review", json={"unit_edits": {f"{pid}:{u['index']}": {"verdict": "error", "error_type": "notation"}}})
    s = client.get(f"/api/activities/{A}/class-summary").json()
    assert calls == [] and s["ai_summary"]["stale"] is True
    r = client.post(f"/api/activities/{A}/class-summary/refresh").json()
    assert calls == [1] and r["ai_summary"]["stale"] is False and r["reteach_focus"].startswith("Practice")
    client.get(f"/api/activities/{A}/class-summary")
    assert calls == [1]


# ======================================================================== B-9 time zone
@pytest.mark.parametrize("hour_utc", [15, 16, 17, 18, 19, 23, 4])
def test_seeded_dashboard_is_the_same_at_any_hour(hour_utc):
    from app.seed import build
    from app.services import core
    from app.store.memory import MemoryStore

    for minute in (0, 1, 30):
        now = datetime(2026, 10, 1, hour_utc, minute, tzinfo=timezone.utc)
        m = MemoryStore("http://x", "k")
        build(m, now=now, with_images=False)
        d = core.dashboard(m, now=now)
        assert d["approved_today"]["value"] == 26 and d["awaiting_review"]["value"] == 12, (hour_utc, minute, d)


# ======================================================================== B-23 roster changes
def test_approved_grade_stays_in_the_gradebook_when_the_student_leaves_the_roster(client):
    sid = next(s["id"] for s in store().select("submissions", activity_id=A) if s["status"] == "approved")
    st = store().get("submissions", sid)["student_id"]
    section = store().get("students", st)["section"]
    store().update("students", st, {"section": "Transferred"})
    try:
        rows = client.get(f"/api/activities/{A}/gradebook").json()["rows"]
        row = next(r for r in rows if r["student_id"] == st)
        assert row["total"] is not None and "not on the class roster" in row["status"]
    finally:
        store().update("students", st, {"section": section})


def test_error_responses_hide_internals(client):
    r = client.patch("/api/submissions/sub-math-2026-014/review", json={"criterion_scores": {"nope::x": 1}})
    assert r.status_code == 409 and "Traceback" not in r.text
    r = client.get("/api/activities/does-not-exist")
    assert r.status_code == 404 and "Traceback" not in r.text
