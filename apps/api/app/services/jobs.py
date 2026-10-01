"""Background batch grading. Progress lives in the submissions table (status) plus an in-process job list."""
from __future__ import annotations

import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor

from ..config import get_settings
from ..grading import grader, llm
from ..grading.scoring import rubric_problems
from ..store.base import Store, new_id, now_iso
from . import notifications, roster
from .core import Bundle, Conflict, NotFound, touch

log = logging.getLogger("tsekmate.jobs")
_jobs: dict[str, dict] = {}
_lock = threading.Lock()
_match_lock = threading.Lock()  # two papers must not claim the same student at the same time
# Parallel grading calls. Kept low to stay under per-minute API rate limits.
WORKERS = max(1, int(os.getenv("GRADING_WORKERS", "2")))


def start(store: Store, activity_id: str, only: str | None = None) -> dict:
    """Grade every uploaded or failed paper of an activity, or just one paper (`only`, used by Grade again)."""
    b = Bundle(store, activity_id)
    errs = rubric_problems(b.rubric, b.rubric_total)
    if errs:  # never grade against a rubric whose points don't add up
        raise Conflict("Fix the rubric before grading. " + " ".join(errs))
    with _lock:
        job = _jobs.get(activity_id)
        if job and job["running"]:
            if only:
                raise Conflict("Grading is already running for this activity. Try again when it finishes.")
            return progress(store, activity_id)
        if only:
            sub = next((x for x in b.subs if x["id"] == only), None)
            if not sub:
                raise NotFound("Paper not found.")
            if sub["status"] not in ("failed", "uploaded"):
                raise Conflict("Only papers that are not graded yet, or whose grading failed, can be graded again.")
            todo = [sub]
        else:
            todo = [x for x in sorted(b.subs, key=lambda x: x["created_at"]) if x["status"] in ("uploaded", "failed")]
        if not todo:
            return progress(store, activity_id)
        ids = [x["id"] for x in todo]
        for sid in ids:
            store.update("submissions", sid, {"status": "grading", "updated_at": now_iso()})
        _jobs[activity_id] = {"ids": ids, "running": True, "checking": set(), "retry": bool(only)}
    threading.Thread(target=_run, args=(store, activity_id, ids, bool(only)), daemon=True).start()
    return progress(store, activity_id)


def _run(store: Store, activity_id: str, ids: list[str], retry: bool = False) -> None:
    try:
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            list(pool.map(lambda sid: _grade_one(store, activity_id, sid), ids))
    finally:
        with _lock:
            _jobs[activity_id]["running"] = False
        touch(store, activity_id)
        try:
            _notify(store, activity_id, ids, retry)
        except Exception:  # notifications must never break grading
            log.exception("could not create grading notification")


def _notify(store: Store, activity_id: str, ids: list[str], retry: bool) -> None:
    b = Bundle(store, activity_id)
    subs = [x for x in b.subs if x["id"] in ids]
    failed = [x for x in subs if x["status"] == "failed"]
    review = [x for x in subs if x["status"] == "needs_review"]
    unidentified = [x for x in subs if not x.get("student_id") and x["status"] != "failed"]
    title = b.activity["title"]
    if retry and subs:
        x = subs[0]
        who = b.student_name(x.get("student_id")) or x.get("student_id") or "Unidentified paper"
        if x["status"] == "failed":
            reason = (b.ai.get(x["id"], {}).get("raw_json") or {}).get("teacher_message", "")
            notifications.add(store, "grading_failed", f"Grade again failed: {who}", f"{title}. {reason}".strip(), link=f"/submissions/{x['id']}", activity_id=activity_id, submission_id=x["id"])
        else:
            notifications.add(store, "regrade_ok", f"Grade again succeeded: {who}", f"{title}. The AI draft is ready for your review.", link=f"/submissions/{x['id']}", activity_id=activity_id, submission_id=x["id"])
        return
    parts = []
    if review:
        parts.append(f"{len(review)} need{'s' if len(review) == 1 else ''} review (low confidence or flags)")
    if unidentified:
        parts.append(f"{len(unidentified)} student{'s' if len(unidentified) != 1 else ''} not identified")
    notifications.add(store, "grading_done", f"Grading finished: {len(subs) - len(failed)} of {len(subs)} paper{'s' if len(subs) != 1 else ''}",
                      f"{title}. " + ("; ".join(parts) + "." if parts else "All drafts are ready to approve."), link=f"/queue?activity={activity_id}", activity_id=activity_id)
    if failed:
        reason = (b.ai.get(failed[0]["id"], {}).get("raw_json") or {}).get("teacher_message", "")
        notifications.add(store, "grading_failed", f"{len(failed)} paper{'s' if len(failed) != 1 else ''} could not be graded",
                          f"{title}. {reason} Open the paper and press Grade again.".strip(), link=f"/submissions/{failed[0]['id']}", activity_id=activity_id, submission_id=failed[0]["id"])


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
    model = get_settings().anthropic_model
    try:
        if not img:
            raise FileNotFoundError("image missing from storage")
        result = grader.grade_image(img[0], img[1], b.activity, b.problems, b.rubric)
    except (llm.LLMUnavailable, llm.LLMError) as e:  # teacher message in str(e), technical reason in e.detail
        log.warning("grading failed for %s: %s", sub_id, e.detail)
        result = grader.failed_result(b.activity, b.problems, b.rubric, model, now_iso(), e.detail, teacher_message=str(e))
    except FileNotFoundError as e:
        result = grader.failed_result(b.activity, b.problems, b.rubric, model, now_iso(), str(e),
                                      teacher_message="The photo for this paper is missing. Delete the paper and upload it again.")
    except Exception as e:  # anything unexpected: the teacher can retry or grade by hand
        log.exception("grading failed for %s", sub_id)
        result = grader.failed_result(b.activity, b.problems, b.rubric, model, now_iso(), f"{type(e).__name__}: {e}",
                                      teacher_message="Something went wrong while grading. Press Grade again, or grade this paper by hand.")
    status = result.pop("status")
    store.insert("ai_results", {"id": f"ai-{new_id()[:12]}", "submission_id": sub_id, **result})
    # a fresh AI result resets any earlier review draft for this paper
    store.delete("teacher_reviews", submission_id=sub_id)
    patch: dict = {"status": status, "updated_at": now_iso()}
    with _match_lock:
        fresh = Bundle(store, s["activity_id"])
        current = store.get("submissions", sub_id) or s
        ident = current.get("identity") or {}
        extracted = result.get("identity") or {}
        if ident.get("method") in ("teacher_upload", "teacher") and current.get("student_id"):
            # the teacher already chose the student; keep it and just record what the paper says
            patch["identity"] = {**ident, "extracted_name": extracted.get("student_name"), "extracted_id": extracted.get("student_id"),
                                 "identity_confidence": extracted.get("identity_confidence", 0)}
        elif status == "failed":
            patch["identity"] = {**ident, "status": "unidentified" if not current.get("student_id") else ident.get("status", "matched"),
                                 "reason": "Grading failed before the name could be read." if not current.get("student_id") else ident.get("reason")}
        else:
            m = roster.match(fresh.roster(), extracted, fresh.taken(), sub_id)
            patch["identity"] = m
            patch["student_id"] = m["student_id"] if m["status"] == "matched" else None
            if m["status"] != "matched" and status == "ready":
                status = patch["status"] = "needs_review"  # the teacher has to pick the student first
        store.update("submissions", sub_id, patch)
    return {"status": status, **result}


def progress(store: Store, activity_id: str) -> dict:
    b = Bundle(store, activity_id)
    errs = rubric_problems(b.rubric, b.rubric_total)
    if errs:  # never grade against a rubric whose points don't add up
        raise Conflict("Fix the rubric before grading. " + " ".join(errs))
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
        items.append({"submission_id": sid, "student_id": s.get("student_id"), "student_name": b.student_name(s.get("student_id")), "state": state})
    done = sum(1 for i in items if i["state"] in ("done", "failed"))
    return {"total": len(items), "done": done, "running": running, "items": items}
