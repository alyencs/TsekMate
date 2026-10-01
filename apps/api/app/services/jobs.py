"""Background batch grading. Progress lives in the submissions table (status) plus an in-process job list."""
from __future__ import annotations

import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor

from ..config import get_settings
from ..grading import grader, llm
from ..store.base import Store, new_id, now_iso
from .core import Bundle, touch

log = logging.getLogger("tsekmate.jobs")
_jobs: dict[str, dict] = {}
_lock = threading.Lock()
# Parallel grading calls. Kept low because Gemini free-tier limits are per minute.
WORKERS = max(1, int(os.getenv("GRADING_WORKERS", "2")))


def start(store: Store, activity_id: str) -> dict:
    b = Bundle(store, activity_id)
    with _lock:
        job = _jobs.get(activity_id)
        if job and job["running"]:
            return progress(store, activity_id)
        todo = [s for s in sorted(b.subs, key=lambda s: s["student_id"]) if s["status"] in ("uploaded", "failed")]
        if not todo:
            return progress(store, activity_id)
        ids = [s["id"] for s in todo]
        for sid in ids:
            store.update("submissions", sid, {"status": "grading", "updated_at": now_iso()})
        _jobs[activity_id] = {"ids": ids, "running": True, "checking": set()}
    threading.Thread(target=_run, args=(store, activity_id, ids), daemon=True).start()
    return progress(store, activity_id)


def _run(store: Store, activity_id: str, ids: list[str]) -> None:
    try:
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            list(pool.map(lambda sid: _grade_one(store, activity_id, sid), ids))
    finally:
        with _lock:
            _jobs[activity_id]["running"] = False
        touch(store, activity_id)


def _grade_one(store: Store, activity_id: str, sub_id: str) -> None:
    with _lock:
        _jobs[activity_id]["checking"].add(sub_id)
    try:
        grade_submission(store, sub_id)
    finally:
        with _lock:
            _jobs[activity_id]["checking"].discard(sub_id)


def grade_submission(store: Store, sub_id: str) -> dict:
    s = store.get("submissions", sub_id)
    b = Bundle(store, s["activity_id"])
    img = store.get_image(s["image_path"]) if s.get("image_path") else None
    try:
        if not img:
            raise ValueError("The image for this paper is missing.")
        result = grader.grade_image(img[0], img[1], b.activity, b.problems, b.rubric)
    except llm.LLMUnavailable as e:
        result = grader.failed_result(b.activity, b.problems, b.rubric, "none", now_iso(), str(e))
    except llm.LLMError as e:  # provider error with a teacher-safe message (quota, bad key, blocked, ...)
        log.warning("grading failed for %s: %s", sub_id, e)
        result = grader.failed_result(b.activity, b.problems, b.rubric, get_settings().gemini_model, now_iso(), str(e))
    except Exception as e:  # network errors, refusals, etc.: the teacher grades this paper by hand
        log.exception("grading failed for %s", sub_id)
        result = grader.failed_result(b.activity, b.problems, b.rubric, "unknown", now_iso(), f"{type(e).__name__}: {e}")
    status = result.pop("status")
    store.insert("ai_results", {"id": f"ai-{new_id()[:12]}", "submission_id": sub_id, **result})
    # a fresh AI result resets any earlier review draft for this paper
    store.delete("teacher_reviews", submission_id=sub_id)
    store.update("submissions", sub_id, {"status": status, "updated_at": now_iso()})
    return {"status": status, **result}


def progress(store: Store, activity_id: str) -> dict:
    b = Bundle(store, activity_id)
    with _lock:
        job = _jobs.get(activity_id)
        ids = list(job["ids"]) if job else [s["id"] for s in b.subs if s["status"] in ("grading", "uploaded")]
        checking = set(job["checking"]) if job else set()
        running = bool(job and job["running"])
    subs = {s["id"]: s for s in b.subs}
    items = []
    for sid in ids:
        s = subs.get(sid)
        if not s:
            continue
        st = s["status"]
        state = "checking" if sid in checking else "waiting" if st in ("grading", "uploaded") else "failed" if st == "failed" else "done"
        items.append({"submission_id": sid, "student_id": s["student_id"], "state": state})
    done = sum(1 for i in items if i["state"] in ("done", "failed"))
    return {"total": len(items), "done": done, "running": running, "items": items}
