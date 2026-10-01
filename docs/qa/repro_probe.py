"""QA audit reproduction probe. Runs against the in-memory store (no API key, no Supabase).

    cd apps/api && python ../../docs/qa/repro_probe.py

Each line prints the observed status code for one finding in docs/QA-AUDIT.md.
"""
import io, os, sys, json
os.environ["ANTHROPIC_API_KEY"] = ""; os.environ["SUPABASE_URL"] = ""  # empty (not unset) so a local .env cannot override them
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "apps" / "api"))
from fastapi.testclient import TestClient
from PIL import Image
from app.main import app
from app.store import get_store
A = "act-linear-eq-quiz1"
def png():
    b = io.BytesIO(); Image.new("RGB",(50,50),(255,255,255)).save(b,"PNG"); return b.getvalue()
with TestClient(app, raise_server_exceptions=False) as c:
    st = get_store()
    print("1 no-auth list activities:", c.get("/api/activities").status_code, "settings patch:", c.patch("/api/settings", json={"grading_mode":"fast"}).status_code)
    # 2 NaN rubric
    body = '{"title":"t","subject":"math","class_name":"X","date":"2026-01-01","problems":[{"order":1,"text":"a","expected_answer":"b"}],"rubric":[{"name":"A","points":NaN}],"rubric_total":NaN}'
    r = c.post("/api/activities", content=body, headers={"content-type":"application/json"})
    print("2 NaN rubric create:", r.status_code)
    print("2b list activities after NaN:", c.get("/api/activities").status_code)
    # cleanup NaN activity
    for a in st.select("activities"):
        if a["title"] == "t": st.delete("activities", id=a["id"]); st.delete("rubrics", activity_id=a["id"]); st.delete("problems", activity_id=a["id"])
    # 3 duplicate student IDs in a single upload
    roster = c.get(f"/api/activities/{A}/roster").json()["students"]
    free = next(s["student_id"] for s in roster if s["status"] == "Not submitted")
    r = c.post(f"/api/activities/{A}/submissions", files=[("files",("a.png",png(),"image/png")),("files",("b.png",png(),"image/png"))], data={"student_ids": f"{free},{free}"})
    print("3 duplicate student in one upload:", r.status_code, [x["student_id"] for x in r.json()] if r.status_code==201 else r.text)
    # 4 unit_edits points_awarded null
    sid = "sub-math-2026-014"
    d = c.get(f"/api/submissions/{sid}").json()
    u = d["ai_result"]["problems"][0]; key = f"{u['problem_id']}:{u['units'][0]['index']}"
    print("4 points_awarded null:", c.patch(f"/api/submissions/{sid}/review", json={"unit_edits": {key: {"points_awarded": None}}}).status_code,
          "points_awarded 'x':", c.patch(f"/api/submissions/{sid}/review", json={"unit_edits": {key: {"points_awarded": "x"}}}).status_code)
    # 5 criterion score NaN
    crit = d["ai_result"]["problems"][0]["criteria_scores"][0]["name"]
    r = c.patch(f"/api/submissions/{sid}/review", content=json.dumps({"criterion_scores": {f"{u['problem_id']}::{crit}": float('nan')}}), headers={"content-type":"application/json"})
    print("5 NaN criterion score:", r.status_code, "then GET:", c.get(f"/api/submissions/{sid}").status_code)
    c.patch(f"/api/submissions/{sid}/review", json={"criterion_scores": {f"{u['problem_id']}::{crit}": None}})
    print("5b after reset GET:", c.get(f"/api/submissions/{sid}").status_code)
    # 6 approve a paper while it is 'grading'
    failed = next((s for s in st.select("submissions", activity_id=A) if s["status"] in ("needs_review","ready") and s.get("student_id")), None)
    st.update("submissions", failed["id"], {"status": "grading"})
    r = c.post(f"/api/submissions/{failed['id']}/approve")
    print("6 approve while grading:", r.status_code, st.get("submissions", failed["id"])["status"])
    # 7 stuck 'grading' (e.g. after restart): regrade / delete / grade all
    st.update("submissions", failed["id"], {"status": "grading"})
    print("7 stuck grading -> regrade:", c.post(f"/api/submissions/{failed['id']}/regrade").status_code,
          "delete:", c.delete(f"/api/submissions/{failed['id']}").status_code,
          "grade-all includes it:", failed["id"] in [i["submission_id"] for i in c.post(f"/api/activities/{A}/grade").json()["items"]])
    # 8 approve an ungraded-by-AI 'failed' paper with zero scores
    # 9 Approve twice
    ok = next(s for s in st.select("submissions", activity_id=A) if s["status"] == "approved")
    print("9 re-approve approved:", c.post(f"/api/submissions/{ok['id']}/approve").status_code)
    # 10 edit an approved paper (changes gradebook without re-approval)
    print("10 edit approved paper:", c.patch(f"/api/submissions/{ok['id']}/review", json={"feedback": {}}).status_code)
    # 11 images endpoint without auth but signed; path traversal style
    print("11 health leaks model:", c.get("/api/health").json())
    # 12 parent message approve on unapproved paper
    print("12 parent approve on unapproved:", c.post(f"/api/submissions/sub-math-2026-014/parent-message/approve", json={"language":"en","text":"hi"}).status_code)
    # 13 adapter exposes grades without auth
    print("13 adapter grades:", c.post("/adapter/grades/draft", json={"activity_id": A}).status_code)
    # 14 queue unknown tab
    print("14 roster of unknown activity:", c.get("/api/activities/nope/roster").status_code)
    # 15 upload with content-type lie
    r = c.post(f"/api/activities/{A}/submissions", files=[("files",("a.jpg",b"<html><script>alert(1)</script></html>","image/jpeg"))])
    print("15 non-image bytes accepted as image/jpeg:", r.status_code, r.json()[0]["quality"] if r.status_code==201 else r.text)
