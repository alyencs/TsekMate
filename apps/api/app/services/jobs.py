"""Background grading of a class set. Progress lives in the submissions table (status) plus an in-process job list.

Fast mode grades papers live, a few at a time. Saver mode ("Grade all" only) sends them through the Batch API at half
the token price; see services/batches.py.

Status rules (the paper row is the source of truth):
- `start` moves uploaded/failed papers to `grading` with a new `grading_attempt` id (compare-and-set on the old status).
- `grade_submission` saves its result only if the paper is still `grading` with the same attempt id (compare-and-set),
  so a stale or duplicate grading run can never overwrite a newer teacher action or a newer attempt.
- `recover_stale` returns papers whose grading run is gone (server restart, crashed thread, a run that never
  finished) to `uploaded` (never graded) or `failed` (with an "interrupted" reason), so they can be graded again or
  deleted. Papers inside a processing Saver batch are never touched. It runs at startup and on every grade, progress,
  regrade, and delete request.
"""
from __future__ import annotations

import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from ..config import get_settings
from ..grading import grader, llm
from ..grading.scoring import rubric_problems
from ..store.base import Store, new_id, now_iso
from . import batches, notifications, roster
from . import settings as app_settings
from .core import Bundle, Conflict, NotFound, assignment_lock, touch

log = logging.getLogger("tsekmate.jobs")
_jobs: dict[str, dict] = {}
_lock = threading.RLock()
_inflight: dict[str, str] = {}  # submission id -> grading attempt being graded by a thread of this process
# Parallel grading calls. Kept low to stay under per-minute API rate limits.
WORKERS = max(1, int(os.getenv("GRADING_WORKERS", "2")))
# A paper marked `grading` by another process (or a thread that died) is treated as abandoned after this long.
# Longer than the slowest live grading (two calls of up to 180 s, each retried up to 3 times by the SDK).
STALE_AFTER = timedelta(minutes=float(os.getenv("GRADING_STALE_MINUTES", "30")))
PROCESS_STARTED = datetime.now(timezone.utc)
INTERRUPTED = "Grading was interrupted before it finished (for example, the server restarted). Press Grade again."


def _dt(iso: str | None) -> datetime | None:
    if not iso:
        return None
    d = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def recover_stale(store: Store, activity_id: str | None = None, now: datetime | None = None) -> list[str]:
    """Release papers stuck in `grading` whose grading run no longer exists. Returns the released paper ids."""
    now = now or datetime.now(timezone.utc)
    stuck = [s for s in store.select("submissions", status="grading") if activity_id is None or s["activity_id"] == activity_id]
    if not stuck:
        return []
    in_batch = {sid for r in batches.processing(store) for sid in r["requests"].values()}
    released: list[str] = []
    for s in stuck:
        with _lock:
            if _inflight.get(s["id"]) is not None:
                continue  # being graded right now by this process
        if s["id"] in in_batch:
            continue  # waiting for a Saver batch; batches.collect finishes it
        started = _dt(s.get("updated_at")) or PROCESS_STARTED
        # Marked by an earlier process (this one restarted), or by anyone long enough ago that the run must be dead.
        if started >= PROCESS_STARTED and now - started < STALE_AFTER:
            continue
        b = Bundle(store, s["activity_id"])
        had_result = s["id"] in b.ai
        patch = {"status": "failed" if had_result else "uploaded", "grading_attempt": None, "updated_at": now_iso()}
        if not store.update_where("submissions", s["id"], patch, status="grading", grading_attempt=s.get("grading_attempt")):
            continue  # it changed meanwhile (finished, or released by another request)
        if had_result:  # the paper had an AI result before (a failed one): record why this run produced nothing
            res = grader.failed_result(b.activity, b.problems, b.rubric, get_settings().anthropic_model, now_iso(),
                                       "grading run abandoned (process restart or crashed worker)", teacher_message=INTERRUPTED)
            res.pop("status")
            store.insert("ai_results", {"id": f"ai-{new_id()[:12]}", "submission_id": s["id"], **res})
        released.append(s["id"])
        log.warning("released paper %s stuck in grading since %s", s["id"], s.get("updated_at"))
    if released:
        by_act: dict[str, int] = {}
        for s in stuck:
            if s["id"] in released:
                by_act[s["activity_id"]] = by_act.get(s["activity_id"], 0) + 1
        for aid, n in by_act.items():
            try:
                title = (store.get("activities", aid) or {}).get("title", "")
                notifications.add(store, "grading_failed", f"Grading was interrupted for {n} paper{'s' if n != 1 else ''}",
                                  f"{title}. Press Grade again to finish them.", link=f"/activities/{aid}/upload", activity_id=aid)
            except Exception:
                log.exception("could not create interruption notification")
    return released


def start(store: Store, activity_id: str, only: str | None = None) -> dict:
    """Grade every uploaded or failed paper of an activity, or just one paper (`only`, used by Grade again)."""
    recover_stale(store, activity_id)
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
        ids = []
        for x in todo:
            attempt = new_id()
            ok = store.update_where("submissions", x["id"], {"status": "grading", "grading_attempt": attempt, "updated_at": now_iso()},
                                    status=x["status"])
            if ok:  # skipped if the paper changed since it was read (approved, deleted, or claimed by another request)
                ids.append(x["id"])
                _inflight[x["id"]] = attempt
        if not ids:
            if only:
                raise Conflict("This paper changed in the meantime. Reload the page and try again.")
            return progress(store, activity_id)
        # Saver mode is for "Grade all" only; Grade again on one paper is always graded right away.
        saver = not only and app_settings.get(store).get("grading_mode") == "saver" and batches.available()
        _jobs[activity_id] = {"ids": ids, "running": True, "checking": set(), "retry": bool(only)}
    threading.Thread(target=_run, args=(store, activity_id, ids, bool(only), saver), daemon=True).start()
    return progress(store, activity_id)


def _run(store: Store, activity_id: str, ids: list[str], retry: bool = False, saver: bool = False) -> None:
    live = ids
    try:
        if saver:
            try:
                live = batches.submit(store, activity_id, ids)
            except Exception:  # a batch that can't be sent must not leave papers stuck: grade them live
                log.exception("could not submit the batch; grading live")
                sent = {sid for r in batches.processing(store, activity_id) for sid in r["requests"].values()}
                live = [sid for sid in ids if sid not in sent]
            with _lock:
                for sid in ids:
                    if sid not in live:
                        _inflight.pop(sid, None)  # owned by the batch now (recover_stale skips batch papers)
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            list(pool.map(lambda sid: _grade_one(store, activity_id, sid), live))
    finally:
        with _lock:
            _jobs[activity_id]["running"] = False
            for sid in live:
                _inflight.pop(sid, None)
        try:
            touch(store, activity_id)
        except Exception:
            log.exception("could not update the activity timestamp")
        if set(live) == set(ids):  # papers that went into a batch are announced when it ends (batches.collect)
            notify_done(store, activity_id, ids, retry)


def notify_done(store: Store, activity_id: str, ids: list[str], retry: bool = False) -> None:
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
        attempt = _inflight.get(sub_id)
    try:
        grade_submission(store, sub_id, attempt=attempt)
    except Exception:  # an unexpected error (for example the database) must not leave the paper in `grading`
        log.exception("grading crashed for %s", sub_id)
        try:
            _fail(store, sub_id, attempt, "Something went wrong while grading. Press Grade again, or grade this paper by hand.")
        except Exception:
            log.exception("could not mark %s as failed; recover_stale will release it", sub_id)
    finally:
        with _lock:
            _jobs[activity_id]["checking"].discard(sub_id)
            _inflight.pop(sub_id, None)


def _fail(store: Store, sub_id: str, attempt: str | None, teacher_message: str) -> None:
    s = store.get("submissions", sub_id)
    if not s:
        return
    b = Bundle(store, s["activity_id"])
    res = grader.failed_result(b.activity, b.problems, b.rubric, get_settings().anthropic_model, now_iso(), "worker crashed", teacher_message=teacher_message)
    res.pop("status")
    _save(store, sub_id, attempt, res, {"status": "failed"})


def _save(store: Store, sub_id: str, attempt: str | None, result: dict, patch: dict) -> bool:
    """Write one grading result if this attempt still owns the paper. Returns False (and writes nothing) otherwise."""
    aid = f"ai-{new_id()[:12]}"
    store.insert("ai_results", {"id": aid, "submission_id": sub_id, **result})
    ok = store.update_where("submissions", sub_id, {**patch, "grading_attempt": None, "updated_at": now_iso()},
                            status="grading", grading_attempt=attempt)
    if not ok:
        store.delete("ai_results", id=aid)  # stale run: leave no trace
        log.warning("discarded a stale grading result for %s (attempt %s)", sub_id, attempt)
        return False
    # a fresh AI result resets any earlier review draft for this paper (edits are refused while it is grading)
    store.delete("teacher_reviews", submission_id=sub_id)
    return True


def grade_submission(store: Store, sub_id: str, first_response=None, attempt: str | None = None) -> dict | None:
    """Grade one paper and save the result. `first_response` is the paper's Batch API reply, when there is one.

    `attempt` is the grading attempt that owns the paper (None: the attempt currently recorded on the paper, which is
    how Saver batches finish their papers). Returns None, without saving, when the paper is no longer grading under
    that attempt."""
    s = store.get("submissions", sub_id)
    if not s or s["status"] != "grading":
        return None
    attempt = attempt if attempt is not None else s.get("grading_attempt")
    if s.get("grading_attempt") != attempt:
        return None
    b = Bundle(store, s["activity_id"])
    img = store.get_image(s["image_path"]) if s.get("image_path") else None
    model = get_settings().anthropic_model
    try:
        if not img:
            raise FileNotFoundError("image missing from storage")
        result = grader.grade_image(img[0], img[1], b.activity, b.problems, b.rubric, first_response=first_response)
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
    patch: dict = {"status": status}
    with assignment_lock:
        fresh = Bundle(store, s["activity_id"])
        current = store.get("submissions", sub_id)
        if not current or current["status"] != "grading" or current.get("grading_attempt") != attempt:
            log.warning("paper %s changed while it was graded; result discarded", sub_id)
            return None
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
        if not _save(store, sub_id, attempt, result, patch):
            return None
    return {"status": status, **result}


def progress(store: Store, activity_id: str) -> dict:
    recover_stale(store, activity_id)
    b = Bundle(store, activity_id)
    errs = rubric_problems(b.rubric, b.rubric_total)
    if errs:  # never grade against a rubric whose points don't add up
        raise Conflict("Fix the rubric before grading. " + " ".join(errs))
    waiting_batches = batches.processing(store, activity_id)
    with _lock:
        job = _jobs.get(activity_id)
        ids = list(job["ids"]) if job else [s["id"] for s in b.subs if s["status"] == "grading"]
        checking = set(job["checking"]) if job else set()
        running = bool(job and job["running"]) or bool(waiting_batches)
    for r in waiting_batches:  # papers of a Saver batch stay listed even after Grade again on another paper
        ids += [sid for sid in r["requests"].values() if sid not in ids]
    # and so does any paper still marked grading (for example by another instance), whatever the last local job was
    ids += [s["id"] for s in b.subs if s["status"] == "grading" and s["id"] not in ids]
    subs = {s["id"]: s for s in b.subs}
    # A paper still `grading` that this process is not grading (another instance, before it counts as stale) keeps
    # the page polling; anything else that is not finished is reported as stopped so the page never polls forever.
    running = running or any(subs.get(sid, {}).get("status") == "grading" for sid in ids)
    items = []
    for sid in ids:
        s = subs.get(sid)
        if not s:
            continue
        st = s["status"]
        if sid in checking:
            state = "checking"
        elif st == "grading":
            state = "waiting"
        elif st == "uploaded":
            state = "stopped"  # released by recover_stale: not graded, Grade all picks it up again
        elif st == "failed":
            state = "failed"
        else:
            state = "done"
        items.append({"submission_id": sid, "student_id": s.get("student_id"), "student_name": b.student_name(s.get("student_id")), "state": state})
    done = sum(1 for i in items if i["state"] in ("done", "failed", "stopped"))
    pending = sum(1 for s in b.subs if s["status"] in ("uploaded", "failed"))
    return {"total": len(items), "done": done, "running": running, "items": items, "pending": pending, "saver": batches.eta(store, activity_id)}
