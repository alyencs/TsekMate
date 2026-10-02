"""QA audit reproduction probe. Runs against the in-memory store (no API key, no Supabase).

    cd apps/api && python ../../docs/qa/repro_probe.py

Each numbered check is one finding from docs/QA-AUDIT.md. The original (pre-fix) observations are recorded in that
file; this script now states the expected safe behavior for each check, prints what it observed, and exits non-zero
if any check fails. Requests are made with a signed-in teacher session unless the check is about unauthenticated
access (an unauthenticated client would make every check trivially return 401).
"""
import io
import json
import os
import sys
from pathlib import Path

# Empty (not unset) so a local .env cannot override them: development mode, memory store, no live AI.
os.environ.update({"ANTHROPIC_API_KEY": "", "SUPABASE_URL": "", "APP_ENV": "development", "AUTH_SECRET": "", "IMAGE_SIGNING_SECRET": "",
                   "DEMO_TEACHER_EMAIL": "areyes@university.edu.ph", "DEMO_TEACHER_PASSWORD": "tsekmate"})
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "api"))
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from app.main import app  # noqa: E402
from app.store import get_store  # noqa: E402

A = "act-linear-eq-quiz1"
results: list[tuple[bool, str, str]] = []
_n = [0]


def check(name: str, ok: bool, observed) -> None:
    results.append((ok, name, str(observed)))
    print(f"{'PASS' if ok else 'FAIL'}  {name}: {observed}")


def png() -> bytes:
    _n[0] += 1
    b = io.BytesIO()
    img = Image.new("RGB", (50, 50), (255, 255, 255))
    img.putpixel((0, 0), (_n[0] % 256, 0, 0))  # a different photo each time
    img.save(b, "PNG")
    return b.getvalue()


def raw(c, method, url, body):
    return c.request(method, url, content=body, headers={"content-type": "application/json"})


with TestClient(app, raise_server_exceptions=False) as anon, TestClient(app, raise_server_exceptions=False) as c:
    st = get_store()
    tok = c.post("/api/auth/signin", json={"email": "areyes@university.edu.ph", "password": "tsekmate"}).json()["token"]
    c.headers["Authorization"] = f"Bearer {tok}"

    # 1 (S-1) no authentication
    codes = [anon.get("/api/activities").status_code, anon.patch("/api/settings", json={"grading_mode": "fast"}).status_code]
    check("1 unauthenticated list activities / settings patch -> 401", codes == [401, 401], codes)

    # 2 (B-3) NaN rubric
    body = '{"title":"t","subject":"math","class_name":"X","date":"2026-01-01","problems":[{"order":1,"text":"a","expected_answer":"b"}],"rubric":[{"name":"A","points":NaN}],"rubric_total":NaN}'
    code = raw(c, "POST", "/api/activities", body).status_code
    check("2 NaN rubric create -> 422", code == 422, code)
    code = c.get("/api/activities").status_code
    check("2b list activities after NaN -> 200", code == 200, code)

    # 3 (B-5) duplicate student in one upload
    section = st.get("activities", A)["class_name"]
    st.insert("students", {"id": "2026-990", "name": "Probe Student", "section": section})
    r = c.post(f"/api/activities/{A}/submissions", files=[("files", ("a.png", png(), "image/png")), ("files", ("b.png", png(), "image/png"))],
               data={"student_ids": "2026-990,2026-990"})
    papers = [s["id"] for s in st.select("submissions", activity_id=A) if s.get("student_id") == "2026-990"]
    check("3 duplicate student in one upload -> 409, no paper created", r.status_code == 409 and not papers, (r.status_code, papers))

    # 4 (B-7) invalid unit edits
    sid = "sub-math-2026-014"
    d = c.get(f"/api/submissions/{sid}").json()
    u = d["ai_result"]["problems"][0]
    key = f"{u['problem_id']}:{u['units'][0]['index']}"
    codes = [c.patch(f"/api/submissions/{sid}/review", json={"unit_edits": {key: {"points_awarded": v}}}).status_code for v in (None, "x")]
    check("4 points_awarded null / 'x' -> 422", codes == [422, 422], codes)

    # 5 (B-3) NaN criterion score
    crit = u["criteria_scores"][0]["name"]
    code = raw(c, "PATCH", f"/api/submissions/{sid}/review", json.dumps({"criterion_scores": {f"{u['problem_id']}::{crit}": float("nan")}})).status_code
    after = c.get(f"/api/submissions/{sid}").status_code
    check("5 NaN criterion score -> 422, paper still loads", (code, after) == (422, 200), (code, after))
    c.patch(f"/api/submissions/{sid}/review", json={"criterion_scores": {f"{u['problem_id']}::{crit}": None}})
    code = c.get(f"/api/submissions/{sid}").status_code
    check("5b paper after reset -> 200", code == 200, code)

    # 6 (B-2) approve while grading
    target = next(s for s in st.select("submissions", activity_id=A) if s["status"] in ("needs_review", "ready") and s.get("student_id"))
    st.update("submissions", target["id"], {"status": "grading", "grading_attempt": "probe"})
    from app.services import jobs  # noqa: E402

    jobs._inflight[target["id"]] = "probe"  # a live grading run owns it
    r = c.post(f"/api/submissions/{target['id']}/approve")
    status = st.get("submissions", target["id"])["status"]
    check("6 approve while grading -> 409, still grading", (r.status_code, status) == (409, "grading"), (r.status_code, status))
    jobs._inflight.pop(target["id"], None)

    # 7 (B-1) stuck grading (left by a previous process)
    st.update("submissions", target["id"], {"status": "grading", "grading_attempt": "lost", "updated_at": "2020-01-01T00:00:00+00:00"})
    r = c.post(f"/api/submissions/{target['id']}/regrade")
    check("7 stuck grading -> Grade again works", r.status_code == 200, r.status_code)
    for _ in range(200):
        if not c.get(f"/api/activities/{A}/grading-progress").json()["running"]:
            break
    status = st.get("submissions", target["id"])["status"]
    check("7b stuck paper no longer grading after retry (failed cleanly without an API key)", status == "failed", status)
    st.update("submissions", target["id"], {"status": "grading", "grading_attempt": "lost", "updated_at": "2020-01-01T00:00:00+00:00"})
    code = c.delete(f"/api/submissions/{target['id']}").status_code
    check("7c stuck paper can be deleted", code == 204, code)

    # 9 / 10 (B-15, B-6) re-approve, edit an approved paper
    ok = next(s for s in st.select("submissions", activity_id=A) if s["status"] == "approved")
    code = c.post(f"/api/submissions/{ok['id']}/approve").status_code
    check("9 re-approve an approved paper (intended: Save and re-approve) -> 200", code == 200, code)
    pid = st.select("problems", activity_id=A)[0]["id"]
    r = c.patch(f"/api/submissions/{ok['id']}/review", json={"criterion_scores": {f"{pid}::{crit}": 0}})
    check("10 editing an approved paper withdraws the approval", r.status_code == 200 and r.json()["status"] != "approved", (r.status_code, r.json().get("status")))

    # 11 (S-4) health
    h = anon.get("/api/health").json()
    check("11 public health shows nothing but ok", h == {"ok": True}, h)

    # 12 (B-16) parent message on unapproved paper
    code = c.post("/api/submissions/sub-math-2026-014/parent-message/approve", json={"language": "en", "text": "hi"}).status_code
    check("12 parent message approve on unapproved paper -> 409", code == 409, code)

    # 13 adapter grades
    codes = (anon.post("/adapter/grades/draft", json={"activity_id": A}).status_code, c.post("/adapter/grades/draft", json={"activity_id": A}).status_code)
    check("13 adapter grades: anonymous 401, teacher 200", codes == (401, 200), codes)

    # 14 unknown activity
    code = c.get("/api/activities/nope/roster").status_code
    check("14 roster of unknown activity -> 404", code == 404, code)

    # 15 (S-5) fake image
    r = c.post(f"/api/activities/{A}/submissions", files=[("files", ("a.jpg", b"<html><script>alert(1)</script></html>", "image/jpeg"))])
    check("15 non-image bytes sent as image/jpeg -> 415", r.status_code == 415, r.status_code)

failed = [r for r in results if not r[0]]
print(f"\n{len(results) - len(failed)} passed, {len(failed)} failed")
sys.exit(1 if failed else 0)
