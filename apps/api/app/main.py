"""TsekMate API (FastAPI)."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import Body, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from .config import get_settings
from .grading import llm
from .models import ActivityIn, AssignStudent, ProfilePatch, ReviewPatch, RubricRequest, SettingsPatch, SignIn
from .services import ai_text, core, jobs, notifications
from .services import settings as app_settings
from .store import get_store
from .store.base import now_iso, new_id, verify_signature

logging.basicConfig(level=logging.INFO)
settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    store = get_store()
    if store.kind == "memory":
        from .seed import build

        counts = build(store)
        logging.getLogger("tsekmate").info("In-memory store seeded: %s", counts)
    app_settings.apply(store)
    yield


app = FastAPI(title="TsekMate API", version="0.1.0", description="AI-assisted, teacher-approved grading of handwritten work.", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_UPLOAD = 10 * 1024 * 1024
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "application/pdf"}


@app.exception_handler(core.NotFound)
async def _nf(_req: Request, e: core.NotFound):
    return JSONResponse(status_code=404, content={"detail": str(e)})


@app.exception_handler(core.Conflict)
async def _cf(_req: Request, e: core.Conflict):
    return JSONResponse(status_code=409, content={"detail": str(e)})


@app.exception_handler(llm.LLMUnavailable)
async def _llm(_req: Request, e: llm.LLMUnavailable):
    return JSONResponse(status_code=503, content={"detail": str(e)})


@app.exception_handler(llm.LLMError)
async def _llm_error(_req: Request, e: llm.LLMError):
    return JSONResponse(status_code=e.status, content={"detail": str(e)})


@app.get("/api/health")
def health():
    s = get_settings()
    return {
        "ok": True,
        "store": get_store().kind,
        "ai_provider": "anthropic",
        "ai": ("configured" if s.anthropic_api_key else "missing ANTHROPIC_API_KEY") if llm.sdk_installed() else "anthropic package not installed (pip install -r apps/api/requirements.txt)",
        "model": s.anthropic_model,
        "demo_mode": s.demo_mode,
    }


@app.post("/api/auth/signin")
def signin(body: SignIn):
    s = get_settings()
    if body.email.strip().lower() != s.teacher_email.lower() or body.password != s.teacher_password:
        raise HTTPException(401, "Email or password is incorrect.")
    p = app_settings.profile(get_store())
    return {"name": p["name"], "email": s.teacher_email, "class_name": p["department"]}


@app.get("/api/dashboard")
def dashboard():
    return core.dashboard(get_store())


@app.get("/api/activities")
def activities():
    return core.list_activities(get_store())


@app.post("/api/activities", status_code=201)
def create_activity(body: ActivityIn):
    return core.create_activity(get_store(), body)


@app.get("/api/activities/{activity_id}")
def activity(activity_id: str):
    return core.activity_full(core.Bundle(get_store(), activity_id))


@app.get("/api/rubric-templates")
def rubric_templates():
    return sorted(get_store().select("rubric_templates"), key=lambda t: t["name"])


@app.get("/api/activities/{activity_id}/submissions")
def submissions(activity_id: str):
    return core.list_uploads(get_store(), activity_id)


@app.post("/api/activities/{activity_id}/submissions", status_code=201)
async def upload(activity_id: str, files: list[UploadFile] = File(...), student_ids: str | None = Form(None)):
    payload = []
    for f in files:
        data = await f.read()
        ctype = (f.content_type or "").lower()
        if ctype == "image/jpg":
            ctype = "image/jpeg"
        if ctype not in ALLOWED_TYPES:
            raise HTTPException(415, f"{f.filename}: only JPG, PNG, WEBP, or PDF files are supported.")
        if len(data) > MAX_UPLOAD:
            raise HTTPException(413, f"{f.filename}: file is larger than 10 MB.")
        if not data:
            raise HTTPException(400, f"{f.filename}: file is empty.")
        payload.append((f.filename or "paper", data, ctype))
    ids = [s.strip() for s in student_ids.split(",") if s.strip()] if student_ids else None
    if ids is not None and len(ids) != len(payload):
        raise HTTPException(400, "student_ids must have one ID per file.")
    return core.add_uploads(get_store(), activity_id, payload, ids)


@app.delete("/api/submissions/{sub_id}", status_code=204)
def delete_submission(sub_id: str):
    core.delete_submission(get_store(), sub_id)
    return Response(status_code=204)


@app.post("/api/activities/{activity_id}/grade")
def grade(activity_id: str):
    return jobs.start(get_store(), activity_id)


@app.post("/api/submissions/{sub_id}/regrade")
def regrade(sub_id: str):
    """Grade again: retry one paper (usually after a failed AI call) with the activity's current rubric and settings."""
    store = get_store()
    s = store.get("submissions", sub_id)
    if not s:
        raise HTTPException(404, "Paper not found.")
    return jobs.start(store, s["activity_id"], only=sub_id)


@app.patch("/api/submissions/{sub_id}/student")
def assign_student(sub_id: str, body: AssignStudent):
    return core.assign_student(get_store(), sub_id, body.student_id.strip())


@app.get("/api/activities/{activity_id}/roster")
def roster(activity_id: str):
    b = core.Bundle(get_store(), activity_id)
    return {"activity": core.activity_summary(b), "students": core.roster_status(b)}


@app.post("/api/rubric/generate")
def generate_rubric(body: RubricRequest):
    """Draft a rubric with AI. The result is a draft for the teacher to edit; nothing is saved here."""
    if not any(p.text.strip() for p in body.problems) and not body.title.strip():
        raise HTTPException(400, "Add a title or at least one problem first, so the AI knows what the rubric is for.")
    return ai_text.generate_rubric(body)


@app.get("/api/notifications")
def list_notifications():
    return notifications.listing(get_store())


@app.post("/api/notifications/read-all")
def read_all_notifications():
    return notifications.mark_read(get_store())


@app.post("/api/notifications/{notification_id}/read")
def read_notification(notification_id: str):
    return notifications.mark_read(get_store(), notification_id)


def _settings_view() -> dict:
    s = get_settings()
    return {
        **app_settings.get(get_store()),
        "ai": {"provider": "Anthropic Claude", "model": s.anthropic_model, "configured": bool(s.anthropic_api_key) and llm.sdk_installed(), "demo_mode": s.demo_mode},
    }


@app.get("/api/settings")
def read_settings():
    return _settings_view()


@app.patch("/api/settings")
def write_settings(body: SettingsPatch):
    r = app_settings.update(get_store(), body.model_dump())
    return {**_settings_view(), "rerouted": r["rerouted"]}


@app.get("/api/profile")
def read_profile():
    store = get_store()
    acts = core.list_activities(store)
    classes = sorted({a["class_name"] for a in acts})
    students = sum(len(store.select("students", section=c)) for c in classes)
    return {
        **app_settings.profile(store),
        "email": get_settings().teacher_email,
        "role": "Teacher",
        "account_status": "Active (single demo teacher account)",
        "activities": len(acts),
        "classes": classes,
        "students": students,
    }


@app.patch("/api/profile")
def write_profile(body: ProfilePatch):
    app_settings.update_profile(get_store(), body.model_dump(exclude_none=True))
    return read_profile()


@app.get("/api/activities/{activity_id}/grading-progress")
def grading_progress(activity_id: str):
    return jobs.progress(get_store(), activity_id)


@app.get("/api/activities/{activity_id}/queue")
def queue(activity_id: str, tab: Literal["needs_review", "ready", "approved", "all"] = "needs_review"):
    return core.queue(get_store(), activity_id, tab)


@app.get("/api/submissions/{sub_id}")
def submission(sub_id: str):
    return core.submission_detail(get_store(), sub_id)


@app.patch("/api/submissions/{sub_id}/review")
def review(sub_id: str, body: ReviewPatch):
    return core.patch_review(get_store(), sub_id, body.unit_edits, body.problem_scores, body.feedback)


@app.post("/api/submissions/{sub_id}/approve")
def approve(sub_id: str):
    return core.approve(get_store(), sub_id)


@app.get("/api/activities/{activity_id}/class-summary")
def class_summary(activity_id: str):
    return core.class_summary(get_store(), activity_id)


@app.post("/api/activities/{activity_id}/practice")
def practice(activity_id: str):
    store = get_store()
    summary = core.class_summary(store, activity_id)
    return ai_text.practice(core.Bundle(store, activity_id), summary["reteach_focus"])


@app.get("/api/activities/{activity_id}/gradebook")
def gradebook(activity_id: str):
    return core.gradebook(get_store(), activity_id)


@app.get("/api/images/{path:path}")
def image(path: str, expires: int = Query(...), sig: str = Query(...)):
    """Signed URLs for the in-memory store (Supabase issues its own signed URLs)."""
    if not verify_signature(path, expires, sig, get_settings().signing_secret):
        raise HTTPException(403, "This image link has expired. Reload the page.")
    img = get_store().get_image(path)
    if not img:
        raise HTTPException(404, "Image not found (it may have been deleted after approval).")
    return Response(content=img[0], media_type=img[1], headers={"Cache-Control": "private, max-age=600"})


# ---------------------------------------------------------------- stretch: parent message
@app.post("/api/submissions/{sub_id}/parent-message")
def parent_message(sub_id: str):
    store = get_store()
    s = store.get("submissions", sub_id)
    if not s:
        raise HTTPException(404, "Paper not found.")
    if s["status"] != "approved":
        raise HTTPException(409, "Approve the grade first. Parent messages are drafted only from approved results.")
    b = core.Bundle(store, s["activity_id"])
    msg = ai_text.parent_message(b, sub_id)
    for lang in ("en", "fil"):
        store.insert("parent_messages", {"id": f"pm-{new_id()[:12]}", "submission_id": sub_id, "language": lang, "text": msg[lang], "approved": False, "sent_at": None, "model": msg["model"], "created_at": now_iso()})
    return {**msg, "approved": False}


class ParentApprove(BaseModel):
    language: Literal["en", "fil"]
    text: str


@app.post("/api/submissions/{sub_id}/parent-message/approve")
def parent_message_approve(sub_id: str, body: ParentApprove):
    store = get_store()
    if not store.get("submissions", sub_id):
        raise HTTPException(404, "Paper not found.")
    if not body.text.strip():
        raise HTTPException(400, "The message is empty.")
    ts = now_iso()
    store.insert("parent_messages", {"id": f"pm-{new_id()[:12]}", "submission_id": sub_id, "language": body.language, "text": body.text.strip(), "approved": True, "sent_at": ts, "model": "teacher-approved", "created_at": ts})
    return {"sent": True, "note": "Mock delivery: recorded through the adapter, not sent to a real parent app or SMS gateway."}


# ---------------------------------------------------------------- adapter (document Section 6.5). NOT an official integration.
@app.get("/adapter/activities")
def adapter_activities():
    return [
        {"external_id": a["id"], "title": a["title"], "class": a["class_name"], "subject": a["subject"], "total_points": a["total_points"], "updated_at": a["updated_at"]}
        for a in core.list_activities(get_store())
    ]


@app.get("/adapter/submissions")
def adapter_submissions(activity_id: str):
    b = core.Bundle(get_store(), activity_id)
    return [{"external_id": s["id"], "student_ref": s["student_id"], "status": s["status"], "submitted_at": s["created_at"]} for s in b.subs]


@app.post("/adapter/grades/draft")
def adapter_grades(body: dict = Body(...)):
    activity_id = body.get("activity_id")
    if not activity_id:
        raise HTTPException(400, "activity_id is required.")
    grades = core.approved_grades(get_store(), activity_id)
    return {"accepted": len(grades), "grades": grades, "note": "Mock adapter: approved grades were packaged as drafts but not sent to any real school system."}


@app.post("/adapter/notifications")
def adapter_notifications(body: dict = Body(...)):
    return {"accepted": True, "note": "Mock adapter: notification recorded, not delivered.", "received": {k: body.get(k) for k in ("submission_id", "language")}}
