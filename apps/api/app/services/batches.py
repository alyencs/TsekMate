"""Saver grading: grade a class set through the Message Batches API, which bills every token at half price.

Results usually arrive within an hour (at most 24 hours), so this is used only for "Grade all" when the teacher picked
the Saver grading mode. "Grade again" on one paper is always graded live.

Each batch is saved in the grading_batches table, so a server restart picks the polling up again. When a batch ends,
every reply goes through the same validation as a live reply (grader.grade_image); a reply that fails validation gets
its one retry as a live call, and papers the batch could not grade are graded live.
"""
from __future__ import annotations

import json
import logging
import os
import statistics
import threading
import time
from datetime import datetime, timedelta, timezone

from ..config import get_settings
from ..grading import grader, llm
from ..store.base import Store, new_id, now_iso

log = logging.getLogger("tsekmate.batches")

POLL_SECONDS = max(5, int(os.getenv("BATCH_POLL_SECONDS", "30")))
MAX_BATCH_BYTES = 100 * 1024 * 1024  # the API allows 256 MB per batch; stay well under it
TYPICAL_SECONDS = 3600  # most batches finish within an hour
MAX_SECONDS = 24 * 3600  # a batch that has not finished after 24 hours expires

_lock = threading.Lock()
_poller: dict = {"thread": None}


def available() -> bool:
    return bool(get_settings().anthropic_api_key) and llm.sdk_installed()


def _parse(iso: str) -> datetime:
    return datetime.fromisoformat(str(iso).replace("Z", "+00:00"))


def submit(store: Store, activity_id: str, ids: list[str]) -> list[str]:
    """Send papers to the Batch API. Returns the ids to grade live instead: no photo, answered by the demo cache, or
    the batch was refused."""
    import anthropic

    from .core import Bundle

    b = Bundle(store, activity_id)
    client = llm._client()
    model = get_settings().anthropic_model
    live: list[str] = []

    def send(chunk: list[tuple[str, dict]]) -> None:
        requests = {f"r{i}": sid for i, (sid, _) in enumerate(chunk)}
        try:
            batch = client.messages.batches.create(requests=[{"custom_id": f"r{i}", "params": params} for i, (_, params) in enumerate(chunk)])
        except anthropic.APIError as e:
            log.warning("batch refused, grading %d papers live instead: %s", len(chunk), llm._map_api_error(e, model).detail)
            live.extend(requests.values())
            return
        store.insert("grading_batches", {
            "id": f"gb-{new_id()[:12]}", "activity_id": activity_id, "provider_batch_id": batch.id, "requests": requests,
            "status": "processing", "total": len(requests), "done": 0, "model": model, "submitted_at": now_iso(), "ended_at": None,
        })
        log.info("batch %s submitted: %d papers for activity %s", batch.id, len(requests), activity_id)

    cur: list[tuple[str, dict]] = []
    size = 0
    for sid in ids:
        s = store.get("submissions", sid)
        img = store.get_image(s["image_path"]) if s and s.get("image_path") else None
        if not img or grader.demo_cached(img[0]):
            live.append(sid)  # the live path records "photo is missing", or answers from the demo cache at no cost
            continue
        params = llm.request_params(grader.build_messages(img[0], img[1], b.activity, b.problems, b.rubric))
        n = len(json.dumps(params))
        if cur and size + n > MAX_BATCH_BYTES:  # send each full chunk right away so a class set never sits in memory
            send(cur)
            cur, size = [], 0
        cur.append((sid, params))
        size += n
    if cur:
        send(cur)
    ensure_poller(store)
    return live


def processing(store: Store, activity_id: str | None = None) -> list[dict]:
    rows = store.select("grading_batches", status="processing")
    return [r for r in rows if activity_id is None or r["activity_id"] == activity_id]


def ensure_poller(store: Store) -> None:
    """Start the background poller if batches are waiting and it is not running."""
    with _lock:
        t = _poller["thread"]
        if t is None or not t.is_alive():
            t = threading.Thread(target=_loop, args=(store,), daemon=True, name="batch-poller")
            _poller["thread"] = t
            t.start()


def _loop(store: Store) -> None:
    while True:
        with _lock:  # checked under the lock so a batch submitted right now is never missed
            rows = processing(store)
            if not rows:
                _poller["thread"] = None
                return
        for row in rows:
            try:
                check(store, row)
            except Exception:  # keep polling the other batches; this one is tried again next round
                log.exception("could not check batch %s", row.get("provider_batch_id"))
        time.sleep(POLL_SECONDS)


def check(store: Store, row: dict) -> None:
    """Update progress for one batch, and grade its papers once it has ended."""
    client = llm._client()
    batch = client.messages.batches.retrieve(row["provider_batch_id"])
    c = batch.request_counts
    done = c.succeeded + c.errored + c.canceled + c.expired
    if batch.processing_status != "ended":
        if done != row["done"]:
            store.update("grading_batches", row["id"], {"done": done})
        return
    collect(store, row, client)


def collect(store: Store, row: dict, client) -> None:
    from . import jobs
    from .core import touch

    results = {r.custom_id: r.result for r in client.messages.batches.results(row["provider_batch_id"])}
    for cid, sid in row["requests"].items():
        sub = store.get("submissions", sid)
        if not sub or sub["status"] != "grading":
            continue  # deleted, or already graded before a restart
        res = results.get(cid)
        if res is not None and res.type == "succeeded":
            jobs.grade_submission(store, sid, first_response=res.message)
        else:  # errored, expired or canceled: grade it live (full price) so the teacher still gets a draft
            log.warning("batch %s: paper %s came back %s; grading it live", row["provider_batch_id"], sid, getattr(res, "type", "missing"))
            jobs.grade_submission(store, sid)
    store.update("grading_batches", row["id"], {"status": "ended", "done": row["total"], "ended_at": now_iso()})
    touch(store, row["activity_id"])
    if store.get("activities", row["activity_id"]):
        jobs.notify_done(store, row["activity_id"], list(row["requests"].values()))


def eta(store: Store, activity_id: str) -> dict | None:
    """What the teacher sees while Saver grading runs: when it was sent and about how long is left.

    The API gives progress counts but no finish time. The estimate uses, in order: the speed so far, how long earlier
    batches took on this server, or the typical "within an hour".
    """
    rows = processing(store, activity_id)
    if not rows:
        return None
    now = datetime.now(timezone.utc)
    submitted = min(_parse(r["submitted_at"]) for r in rows)
    total = sum(int(r["total"]) for r in rows)
    done = sum(int(r["done"]) for r in rows)
    elapsed = (now - submitted).total_seconds()
    past = [
        (_parse(r["ended_at"]) - _parse(r["submitted_at"])).total_seconds()
        for r in store.select("grading_batches", status="ended") if r.get("ended_at")
    ][-20:]
    if 0 < done < total and elapsed >= 60:
        expected, basis = elapsed * total / done, "progress"
    elif past:
        expected, basis = statistics.median(past), "history"
    else:
        expected, basis = TYPICAL_SECONDS, "typical"
    overdue = elapsed > expected
    return {
        "submitted_at": submitted.isoformat(),
        "eta_seconds": None if overdue else max(60, int(expected - elapsed)),
        "eta_basis": basis,
        "overdue": overdue,
        "deadline": (submitted + timedelta(seconds=MAX_SECONDS)).isoformat(),
        "in_batch": total - done,
    }
