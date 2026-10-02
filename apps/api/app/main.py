"""TsekMate API (FastAPI).

Every route is protected (teacher sign-in required) except the few on `app` itself:
  GET  /api/health          liveness only ({"ok": true}); setup details are at the protected /api/admin/health
  POST /api/auth/signin     returns the session token
  GET  /api/images/{path}   only with a valid, expiring HMAC signature issued to a signed-in teacher
Protected routes are declared on `api` (an APIRouter whose dependency is auth.require_teacher), so a new route is
protected unless someone deliberately puts it on `app`. tests/test_auth.py checks every registered route.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import APIRouter, Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from . import auth
from .config import get_settings
from .grading import llm
from .models import (
    ActivityIn,
    AdapterGradesRequest,
    AdapterNotification,
    AssignStudent,
    ParentApprove,
    ProfilePatch,
    ReviewPatch,
    RubricRequest,
    RubricUpdate,
    SettingsPatch,
    SignIn,
)
from .services import ai_text, core, jobs, notifications, uploads
from .services import settings as app_settings
from .store import get_store
from .store.base import UniqueViolation, new_id, now_iso, verify_signature

logging.basicConfig(level=logging.INFO)
settings = get_settings()
PUBLIC_ROUTES = {("GET", "/api/health"), ("POST", "/api/auth/signin"), ("GET", "/api/images/{path:path}")}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    store = get_store()
    if store.kind == "memory" and not store.select("activities"):  # seed once per process (tests reuse the store)
        from .seed import build

        counts = build(store)
        logging.getLogger("tsekmate").info("In-memory store seeded: %s", counts)
    app_settings.apply(store)
    released = jobs.recover_stale(store)  # papers left in `grading` by a previous process
    if released:
        logging.getLogger("tsekmate").warning("released %d paper(s) left in grading by an earlier run", len(released))
    if jobs.batches.processing(store):  # Saver grading sent before a restart: keep checking for its results
        jobs.batches.ensure_poller(store)
    yield


_docs = {} if not settings.is_production else {"docs_url": None, "redoc_url": None, "openapi_url": None}
app = FastAPI(title="TsekMate API", version="0.2.0", description="AI-assisted, teacher-approved grading of handwritten work.", lifespan=lifespan, **_docs)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("X-Frame-Options", "DENY")
    if request.url.path.startswith("/api/") and not request.url.path.startswith("/api/images/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


api = APIRouter(dependencies=[Depends(auth.require_teacher)])


@app.exception_handler(RequestValidationError)
async def _invalid(_req: Request, e: RequestValidationError):
    """422 without echoing the submitted values: they can be NaN/Infinity (not valid JSON, which made the default
    handler fail with a 500) or text the client should not get back."""
    errors = [{"type": err.get("type"), "loc": list(err.get("loc", ())), "msg": err.get("msg")} for err in e.errors()]
    return JSONResponse(status_code=422, content={"detail": errors})


@app.exception_handler(core.NotFound)
async def _nf(_req: Request, e: core.NotFound):
    return JSONResponse(status_code=404, content={"detail": str(e)})


@app.exception_handler(core.Conflict)
async def _cf(_req: Request, e: core.Conflict):
    return JSONResponse(status_code=409, content={"detail": str(e)})


@app.exception_handler(UniqueViolation)
async def _uv(_req: Request, _e: UniqueViolation):
    return JSONResponse(status_code=409, content={"detail": "That student already has a paper for this activity."})


@app.exception_handler(llm.LLMUnavailable)
async def _llm(_req: Request, e: llm.LLMUnavailable):
    logging.getLogger("tsekmate").warning("AI unavailable: %s", e.detail)
    return JSONResponse(status_code=503, content={"detail": str(e)})


@app.exception_handler(llm.LLMError)
async def _llm_error(_req: Request, e: llm.LLMError):
    logging.getLogger("tsekmate").warning("AI error: %s", e.detail)
    return JSONResponse(status_code=e.status, content={"detail": str(e)})


# ---------------------------------------------------------------- public
@app.get("/api/health")
def health():
    """Liveness only. Store, AI and model details are at the protected /api/admin/health."""
    return {"ok": True}


@app.post("/api/auth/signin")
def signin(body: SignIn, request: Request):
    if auth.throttled(request):
        raise HTTPException(429, "Too many sign-in attempts. Wait a few minutes, then try again.")
    if not auth.check_password(body.email, body.password):
        auth.record_failure(request)
        raise HTTPException(401, "Email or password is incorrect.")
    auth.clear_failures(request)
    token, exp = auth.issue_token()
    p = app_settings.profile(get_store())
    return {"name": p["name"], "email": get_settings().teacher_email, "class_name": p["department"], "token": token, "expires_at": exp}


@app.get("/api/images/{path:path}")
def image(path: str, expires: int = Query(...), sig: str = Query(...)):
    """Signed URLs for the in-memory store (Supabase issues its own signed URLs). Links are issued only inside
    authenticated responses and expire after an hour."""
    if not verify_signature(path, expires, sig, get_settings().signing_secret):
        raise HTTPException(403, "This image link has expired. Reload the page.")
    img = get_store().get_image(path)
    if not img:
        raise HTTPException(404, "Image not found (it may have been deleted after approval).")
    return Response(content=img[0], media_type=img[1], headers={"Cache-Control": "private, max-age=600"})


# ---------------------------------------------------------------- session
@api.get("/api/auth/me")
def me(teacher: auth.Teacher = Depends(auth.require_teacher)):
    p = app_settings.profile(get_store())
    return {"name": p["name"], "email": teacher.email, "class_name": p["department"], "expires_at": teacher.expires}


@api.post("/api/auth/signout", status_code=204)
def signout(teacher: auth.Teacher = Depends(auth.require_teacher)):
    auth.revoke(teacher)
    return Response(status_code=204)


@api.get("/api/admin/health")
def admin_health():
    s = get_settings()
    return {
        "ok": True,
        "store": get_store().kind,
        "ai_provider": "anthropic",
        "ai": ("configured" if s.anthropic_api_key else "missing ANTHROPIC_API_KEY") if llm.sdk_installed() else "anthropic package not installed (pip install -r apps/api/requirements.txt)",
        "model": s.anthropic_model,
        "demo_mode": s.demo_mode,
        "app_env": s.app_env,
    }


# ---------------------------------------------------------------- activities
@api.get("/api/dashboard")
def dashboard():
    return core.dashboard(get_store())


@api.get("/api/activities")
def activities():
    return core.list_activities(get_store())


@api.post("/api/activities", status_code=201)
def create_activity(body: ActivityIn):
    return core.create_activity(get_store(), body)


@api.get("/api/activities/{activity_id}")
def activity(activity_id: str):
    return core.activity_full(core.Bundle(get_store(), activity_id))


@api.patch("/api/activities/{activity_id}/rubric")
def update_rubric(activity_id: str, body: RubricUpdate):
    """Edit the rubric before grading starts. Refused once any paper is graded, so one rubric scores the whole class."""
    return core.update_rubric(get_store(), activity_id, [c.model_dump() for c in body.criteria], body.total_points)


@api.get("/api/rubric-templates")
def rubric_templates():
    return sorted(get_store().select("rubric_templates"), key=lambda t: t["name"])


@api.get("/api/activities/{activity_id}/submissions")
def submissions(activity_id: str):
    return core.list_uploads(get_store(), activity_id)


async def _read_limited(f: UploadFile) -> bytes:
    """Read one upload in chunks, stopping just past the size limit instead of buffering a huge file."""
    out = bytearray()
    while chunk := await f.read(1024 * 1024):
        out += chunk
        if len(out) > uploads.MAX_UPLOAD:
            break
    return bytes(out)


@api.post("/api/activities/{activity_id}/submissions", status_code=201)
async def upload(activity_id: str, files: list[UploadFile] = File(...), student_ids: str | None = Form(None)):
    if len(files) > uploads.MAX_FILES:
        raise HTTPException(413, f"Upload at most {uploads.MAX_FILES} files at a time.")
    payload = []
    for f in files:
        name = (f.filename or "paper")[:200]
        data = await _read_limited(f)
        try:
            ctype = await run_in_threadpool(uploads.validate, name, data)  # checks the bytes, not the declared type
        except uploads.UploadRejected as e:
            raise HTTPException(e.status, str(e)) from None
        payload.append((name, data, ctype))
    ids = [s.strip() for s in student_ids.split(",") if s.strip()] if student_ids else None
    if ids is not None and len(ids) != len(payload):
        raise HTTPException(400, "student_ids must have one ID per file.")
    # Storage writes and the image quality check are blocking: keep them off the event loop.
    return await run_in_threadpool(core.add_uploads, get_store(), activity_id, payload, ids)


@api.delete("/api/submissions/{sub_id}", status_code=204)
def delete_submission(sub_id: str):
    store = get_store()
    s = store.get("submissions", sub_id)
    if s and s["status"] == "grading":
        jobs.recover_stale(store, s["activity_id"])  # a paper stuck in grading can be deleted once released
    core.delete_submission(store, sub_id)
    return Response(status_code=204)


@api.post("/api/activities/{activity_id}/grade")
def grade(activity_id: str):
    return jobs.start(get_store(), activity_id)


@api.post("/api/submissions/{sub_id}/regrade")
def regrade(sub_id: str):
    """Grade again: retry one paper (usually after a failed AI call) with the activity's current rubric and settings."""
    store = get_store()
    s = store.get("submissions", sub_id)
    if not s:
        raise HTTPException(404, "Paper not found.")
    return jobs.start(store, s["activity_id"], only=sub_id)


@api.patch("/api/submissions/{sub_id}/student")
def assign_student(sub_id: str, body: AssignStudent):
    return core.assign_student(get_store(), sub_id, body.student_id.strip())


@api.get("/api/activities/{activity_id}/roster")
def roster(activity_id: str):
    b = core.Bundle(get_store(), activity_id)
    return {"activity": core.activity_summary(b), "students": core.roster_status(b)}


@api.post("/api/rubric/generate")
def generate_rubric(body: RubricRequest):
    """Draft a rubric with AI. The result is a draft for the teacher to edit; nothing is saved here."""
    if not any(p.text.strip() for p in body.problems) and not body.title.strip():
        raise HTTPException(400, "Add a title or at least one problem first, so the AI knows what the rubric is for.")
    return ai_text.generate_rubric(body)


@api.get("/api/notifications")
def list_notifications():
    return notifications.listing(get_store())


@api.post("/api/notifications/read-all")
def read_all_notifications():
    return notifications.mark_read(get_store())


@api.post("/api/notifications/{notification_id}/read")
def read_notification(notification_id: str):
    return notifications.mark_read(get_store(), notification_id)


def _settings_view() -> dict:
    s = get_settings()
    return {
        **app_settings.get(get_store()),
        # Teacher-facing: only whether AI grading is available. Model/provider stay in server config and logs.
        "ai": {"available": bool(s.anthropic_api_key) and llm.sdk_installed(), "demo_mode": s.demo_mode},
    }


@api.get("/api/settings")
def read_settings():
    return _settings_view()


@api.patch("/api/settings")
def write_settings(body: SettingsPatch):
    r = app_settings.update(get_store(), body.model_dump())
    return {**_settings_view(), "rerouted": r["rerouted"]}


@api.get("/api/profile")
def read_profile():
    store = get_store()
    acts = core.list_activities(store)
    classes = sorted({a["class_name"] for a in acts})
    students = sum(len(store.select("students", section=c)) for c in classes)
    return {
        **app_settings.profile(store),
        "email": get_settings().teacher_email,
        "role": "Teacher",
        "account_status": "Active",
        "activities": len(acts),
        "classes": classes,
        "students": students,
    }


@api.patch("/api/profile")
def write_profile(body: ProfilePatch):
    app_settings.update_profile(get_store(), body.model_dump(exclude_none=True))
    return read_profile()


@api.get("/api/activities/{activity_id}/grading-progress")
def grading_progress(activity_id: str):
    return jobs.progress(get_store(), activity_id)


@api.get("/api/activities/{activity_id}/queue")
def queue(activity_id: str, tab: Literal["needs_review", "ready", "approved", "all"] = "needs_review"):
    return core.queue(get_store(), activity_id, tab)


@api.get("/api/submissions/{sub_id}")
def submission(sub_id: str):
    return core.submission_detail(get_store(), sub_id)


@api.patch("/api/submissions/{sub_id}/review")
def review(sub_id: str, body: ReviewPatch):
    unit_edits = {k: v.model_dump(exclude_unset=True) for k, v in body.unit_edits.items()} if body.unit_edits is not None else None
    return core.patch_review(get_store(), sub_id, unit_edits, body.criterion_scores, body.feedback)


@api.post("/api/submissions/{sub_id}/approve")
def approve(sub_id: str):
    return core.approve(get_store(), sub_id)


@api.get("/api/activities/{activity_id}/class-summary")
def class_summary(activity_id: str):
    """Counts plus the cached AI summary. Never calls the AI (see the refresh route)."""
    return core.class_summary(get_store(), activity_id)


@api.post("/api/activities/{activity_id}/class-summary/refresh")
def class_summary_refresh(activity_id: str):
    """One AI call that names the misconceptions in the current errors; the teacher asks for it explicitly."""
    return core.class_summary(get_store(), activity_id, refresh=True)


@api.post("/api/activities/{activity_id}/practice")
def practice(activity_id: str):
    store = get_store()
    summary = core.class_summary(store, activity_id)
    return ai_text.practice(core.Bundle(store, activity_id), summary["reteach_focus"])


@api.get("/api/activities/{activity_id}/gradebook")
def gradebook(activity_id: str):
    return core.gradebook(get_store(), activity_id)


# ---------------------------------------------------------------- stretch: parent message
def _approved_submission(sub_id: str) -> dict:
    s = get_store().get("submissions", sub_id)
    if not s:
        raise HTTPException(404, "Paper not found.")
    if s["status"] != "approved":
        raise HTTPException(409, "Approve the grade first. Parent messages are drafted only from approved results.")
    return s


@api.get("/api/submissions/{sub_id}/parent-message")
def parent_message_latest(sub_id: str):
    """The latest saved drafts (no AI call). Empty strings when nothing was drafted yet."""
    _approved_submission(sub_id)
    rows = sorted(get_store().select("parent_messages", submission_id=sub_id), key=lambda r: r["created_at"])
    drafts = {r["language"]: r for r in rows if not r.get("approved")}
    sent = [r for r in rows if r.get("approved")]
    return {"en": (drafts.get("en") or {}).get("text", ""), "fil": (drafts.get("fil") or {}).get("text", ""), "approved": False,
            "drafted": bool(drafts), "last_approved_at": sent[-1]["sent_at"] if sent else None}


@api.post("/api/submissions/{sub_id}/parent-message")
def parent_message(sub_id: str):
    """Draft a new parent message with AI (only when the teacher asks for one)."""
    s = _approved_submission(sub_id)
    store = get_store()
    b = core.Bundle(store, s["activity_id"])
    msg = ai_text.parent_message(b, sub_id)
    for lang in ("en", "fil"):
        store.insert("parent_messages", {"id": f"pm-{new_id()[:12]}", "submission_id": sub_id, "language": lang, "text": msg[lang], "approved": False, "sent_at": None, "model": msg["model"], "created_at": now_iso()})
    return {"en": msg["en"], "fil": msg["fil"], "approved": False, "drafted": True}


@api.post("/api/submissions/{sub_id}/parent-message/approve")
def parent_message_approve(sub_id: str, body: ParentApprove):
    """Rule: a parent message can be approved only for a paper whose grade is approved (same rule as drafting)."""
    _approved_submission(sub_id)
    if not body.text.strip():
        raise HTTPException(400, "The message is empty.")
    ts = now_iso()
    get_store().insert("parent_messages", {"id": f"pm-{new_id()[:12]}", "submission_id": sub_id, "language": body.language, "text": body.text.strip(), "approved": True, "sent_at": ts, "model": "teacher-approved", "created_at": ts})
    return {"sent": True, "note": "Practice run only: the message was saved but not sent to the parent."}


# ---------------------------------------------------------------- adapter (document Section 6.5). NOT an official integration.
# The adapter returns student IDs and grades, so it requires the teacher session like every other data route.
@api.get("/adapter/activities")
def adapter_activities():
    return [
        {"external_id": a["id"], "title": a["title"], "class": a["class_name"], "subject": a["subject"], "total_points": a["total_points"], "updated_at": a["updated_at"]}
        for a in core.list_activities(get_store())
    ]


@api.get("/adapter/submissions")
def adapter_submissions(activity_id: str):
    b = core.Bundle(get_store(), activity_id)
    return [{"external_id": s["id"], "student_ref": s["student_id"], "status": s["status"], "submitted_at": s["created_at"]} for s in b.subs]


@api.post("/adapter/grades/draft")
def adapter_grades(body: AdapterGradesRequest):
    grades = core.approved_grades(get_store(), body.activity_id)
    return {"accepted": len(grades), "grades": grades, "note": "Practice run only: the grades were prepared but not sent to your school's grading system."}


@api.post("/adapter/notifications")
def adapter_notifications(body: AdapterNotification):
    return {"accepted": True, "note": "Mock adapter: notification recorded, not delivered.", "received": body.model_dump()}


app.include_router(api)
