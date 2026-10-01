"""Business logic shared by the API routes. Everything a teacher sees is computed here from stored rows."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from ..config import get_settings
from ..grading.flags import error_label
from ..grading.scoring import apply_edits, focus_problem, paper_confidence, queue_chips
from ..models import ERROR_TYPES, ActivityIn
from ..store.base import Store, new_id, now_iso


class NotFound(Exception):
    pass


class Conflict(Exception):
    pass


TZ = ZoneInfo(os.getenv("APP_TIMEZONE", "Asia/Manila"))
GRADED = ("needs_review", "ready", "approved", "failed")
PROBLEM_PREFIX = {"math": "P", "science": "P", "grammar": "I"}


def _dt(iso: str | None) -> datetime | None:
    if not iso:
        return None
    d = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _r1(x: float) -> float:
    return round(x + 1e-9, 1)


# ---------------------------------------------------------------- activity bundles
class Bundle:
    """All rows for one activity, loaded with a handful of queries."""

    def __init__(self, store: Store, activity_id: str) -> None:
        a = store.get("activities", activity_id)
        if not a:
            raise NotFound(f"Activity {activity_id} was not found.")
        self.store = store
        self.activity = a
        self.problems = sorted(store.select("problems", activity_id=activity_id), key=lambda p: p["position"])
        r = store.one("rubrics", activity_id=activity_id)
        self.rubric = r["criteria"] if r else []
        self.subs = store.select("submissions", activity_id=activity_id)
        ids = [s["id"] for s in self.subs]
        ai = store.select_in("ai_results", "submission_id", ids)
        self.ai: dict[str, dict] = {}
        for row in sorted(ai, key=lambda r: r["created_at"]):
            self.ai[row["submission_id"]] = row  # latest wins
        self.reviews = {r["submission_id"]: r for r in store.select_in("teacher_reviews", "submission_id", ids)}

    @property
    def subject(self) -> str:
        return self.activity["subject"]

    def effective(self, sub_id: str) -> list[dict]:
        """AI problem results with the teacher's unit edits applied (scores recomputed in code)."""
        ai = self.ai.get(sub_id)
        if not ai:
            return []
        edits = (self.reviews.get(sub_id) or {}).get("unit_edits") or {}
        out = []
        for p in ai["problem_results"]:
            e = apply_edits(p, edits, self.rubric) if p.get("units") else dict(p)
            e["ai_suggested_score"] = p["suggested_score"]
            out.append(e)
        return out

    def problem_finals(self, sub_id: str) -> dict[str, float]:
        overrides = (self.reviews.get(sub_id) or {}).get("problem_scores") or {}
        out = {}
        for p in self.effective(sub_id):
            v = overrides.get(p["problem_id"])
            out[p["problem_id"]] = float(v) if v is not None else float(p["suggested_score"])
        return out

    def final_total(self, sub_id: str) -> float:
        return round(sum(self.problem_finals(sub_id).values()), 2)

    def students(self) -> list[str]:
        return sorted(s["id"] for s in self.store.select("students", section=self.activity["class_name"]))

    def problem_label(self, problem_id: str) -> str:
        p = next((p for p in self.problems if p["id"] == problem_id), None)
        if not p:
            return problem_id
        return f"Item {p['position']}" if self.subject == "grammar" else f"P{p['position']}"


def activity_summary(b: Bundle) -> dict:
    a = b.activity
    st = [s["status"] for s in b.subs]
    return {
        "id": a["id"],
        "title": a["title"],
        "subject": a["subject"],
        "class_name": a["class_name"],
        "date": str(a["date"]),
        "total_points": float(a["total_points"]),
        "papers": len(b.subs),
        "to_review": sum(1 for x in st if x in ("needs_review", "ready", "failed")),
        "flagged": sum(1 for x in st if x in ("needs_review", "failed")),
        "approved": sum(1 for x in st if x == "approved"),
        "updated_at": a["updated_at"],
    }


def activity_full(b: Bundle) -> dict:
    return {
        **activity_summary(b),
        "settings": b.activity.get("settings") or {},
        "problems": [
            {
                "id": p["id"],
                "order": p["position"],
                "text": p["text"],
                "expected_answer": p["expected_answer"],
                "sample_solution": p.get("sample_solution") or "",
                "rule": p.get("rule") or "",
            }
            for p in b.problems
        ],
        "rubric": b.rubric,
    }


def list_activities(store: Store) -> list[dict]:
    out = [activity_summary(Bundle(store, a["id"])) for a in store.select("activities")]
    return sorted(out, key=lambda a: a["updated_at"], reverse=True)


def create_activity(store: Store, data: ActivityIn) -> dict:
    aid = f"act-{new_id()[:8]}"
    total = sum(c.points for c in data.rubric) * len(data.problems)
    ts = now_iso()
    store.insert(
        "activities",
        {
            "id": aid,
            "title": data.title.strip(),
            "subject": data.subject,
            "class_name": data.class_name,
            "date": data.date,
            "settings": data.settings.model_dump(),
            "total_points": total,
            "created_at": ts,
            "updated_at": ts,
        },
    )
    store.insert(
        "problems",
        [
            {
                "id": f"{aid}-p{i + 1}",
                "activity_id": aid,
                "position": i + 1,
                "text": p.text.strip(),
                "expected_answer": p.expected_answer.strip(),
                "sample_solution": p.sample_solution.strip(),
                "rule": p.rule.strip(),
            }
            for i, p in enumerate(sorted(data.problems, key=lambda p: p.order))
        ],
    )
    store.insert("rubrics", {"id": f"{aid}-rubric", "activity_id": aid, "criteria": [c.model_dump() for c in data.rubric]})
    return activity_full(Bundle(store, aid))


def touch(store: Store, activity_id: str) -> None:
    store.update("activities", activity_id, {"updated_at": now_iso()})


# ---------------------------------------------------------------- dashboard
def dashboard(store: Store) -> dict:
    acts = list_activities(store)
    badge = sum(a["flagged"] for a in acts)
    now_local = datetime.now(TZ)
    midnight = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    yday = midnight - timedelta(days=1)
    reviews = store.select("teacher_reviews", approved=True)
    approved_today = sum(1 for r in reviews if (d := _dt(r.get("approved_at"))) and d >= midnight)
    approved_yday = sum(1 for r in reviews if (d := _dt(r.get("approved_at"))) and yday <= d < midnight)
    active = next((a for a in acts if a["to_review"] > 0), acts[0] if acts else None)
    if not active:
        empty = {"value": 0, "delta": 0}
        return {"activity_id": None, "awaiting_review": empty, "flagged": empty, "approved_today": {"value": approved_today, "delta": approved_today - approved_yday}, "class_average": {"value": 0, "out_of": 0, "delta_pct": 0}, "queue_badge": badge}
    b = Bundle(store, active["id"])
    day_ago = datetime.now(timezone.utc) - timedelta(hours=24)
    awaiting = [s for s in b.subs if s["status"] in ("needs_review", "ready", "failed")]
    flagged = [s for s in awaiting if s["status"] in ("needs_review", "failed")]

    def new(subs: list[dict]) -> int:
        return sum(1 for s in subs if (ai := b.ai.get(s["id"])) and _dt(ai["created_at"]) >= day_ago)

    avg, out_of = class_average(b)
    delta_pct = 0
    prev = [a for a in acts if a["subject"] == active["subject"] and a["id"] != active["id"] and a["approved"] > 0 and a["date"] <= active["date"]]
    if prev and avg and out_of:
        pb = Bundle(store, sorted(prev, key=lambda a: a["date"])[-1]["id"])
        pavg, pout = class_average(pb)
        if pavg and pout:
            delta_pct = round((avg / out_of - pavg / pout) / (pavg / pout) * 100)
    return {
        "activity_id": active["id"],
        "awaiting_review": {"value": len(awaiting), "delta": new(awaiting)},
        "flagged": {"value": len(flagged), "delta": new(flagged)},
        "approved_today": {"value": approved_today, "delta": approved_today - approved_yday},
        "class_average": {"value": round(avg) if avg else 0, "out_of": out_of, "delta_pct": delta_pct},
        "queue_badge": badge,
    }


def class_average(b: Bundle) -> tuple[float, float]:
    approved = [s for s in b.subs if s["status"] == "approved"]
    out_of = float(b.activity["total_points"])
    if not approved:
        return 0.0, out_of
    return sum(b.final_total(s["id"]) for s in approved) / len(approved), out_of


# ---------------------------------------------------------------- uploads
def list_uploads(store: Store, activity_id: str) -> list[dict]:
    b = Bundle(store, activity_id)
    out = []
    for s in sorted(b.subs, key=lambda s: s["student_id"]):
        out.append(
            {
                "id": s["id"],
                "student_id": s["student_id"],
                "status": s["status"],
                "image_url": store.signed_url(s["image_path"]) if s.get("image_path") else None,
                "quality": s.get("quality"),
            }
        )
    return out


def add_uploads(store: Store, activity_id: str, files: list[tuple[str, bytes, str]], student_ids: list[str] | None = None) -> list[dict]:
    from .quality import check

    b = Bundle(store, activity_id)
    taken = {s["student_id"] for s in b.subs}
    roster = b.students()
    if student_ids:
        bad = [s for s in student_ids if s not in roster]
        if bad:
            raise Conflict(f"Unknown student ID(s) for {b.activity['class_name']}: {', '.join(bad)}")
        dup = [s for s in student_ids if s in taken]
        if dup:
            raise Conflict(f"{', '.join(dup)} already has a paper for this activity. Delete it first to upload a retake.")
        ids = student_ids
    else:
        free = [s for s in roster if s not in taken]
        if len(free) < len(files):
            raise Conflict(
                f"Only {len(free)} student ID(s) are free in {b.activity['class_name']}. Delete a paper (for example one marked "
                "'Retake suggested') before uploading more."
            )
        ids = free[: len(files)]
    created = []
    for (name, data, ctype), sid in zip(files, ids):
        sub_id = f"sub-{new_id()[:12]}"
        ext = {"image/png": "png", "image/webp": "webp", "application/pdf": "pdf"}.get(ctype, "jpg")
        path = f"uploads/{activity_id}/{sub_id}.{ext}"
        store.put_image(path, data, ctype)
        q = check(data) if ctype.startswith("image/") else {"ok": True, "reason": None}
        ts = now_iso()
        row = {
            "id": sub_id,
            "activity_id": activity_id,
            "student_id": sid,
            "image_path": path,
            "image_hash": hashlib.sha256(data).hexdigest(),
            "status": "uploaded",
            "quality": q,
            "created_at": ts,
            "updated_at": ts,
        }
        store.insert("submissions", row)
        created.append({"id": sub_id, "student_id": sid, "status": "uploaded", "image_url": store.signed_url(path), "quality": q})
    touch(store, activity_id)
    return created


def delete_submission(store: Store, sub_id: str) -> None:
    s = store.get("submissions", sub_id)
    if not s:
        raise NotFound("Paper not found.")
    if s["status"] == "approved":
        raise Conflict("This paper is already approved and in the gradebook, so it cannot be deleted here.")
    if s["status"] == "grading":
        raise Conflict("This paper is being checked right now. Try again in a moment.")
    if s.get("image_path"):
        store.delete_image(s["image_path"])
    for t in ("ai_results", "teacher_reviews", "parent_messages"):
        store.delete(t, submission_id=sub_id)
    store.delete("submissions", id=sub_id)
    touch(store, s["activity_id"])


# ---------------------------------------------------------------- queue
def queue(store: Store, activity_id: str, tab: str) -> dict:
    b = Bundle(store, activity_id)
    tabs = {"needs_review": ("needs_review", "failed"), "ready": ("ready",), "approved": ("approved",), "all": GRADED + ("uploaded", "grading")}
    if tab not in tabs:
        raise NotFound(f"Unknown tab '{tab}'.")
    counts = {k: sum(1 for s in b.subs if s["status"] in v) for k, v in tabs.items()}
    rows = []
    for s in b.subs:
        if s["status"] not in tabs[tab]:
            continue
        rows.append(queue_row(b, s))
    rows.sort(key=lambda r: (r["confidence"] if r["confidence"] is not None else -1, r["student_id"]))
    return {"activity": activity_summary(b), "counts": counts, "rows": rows}


def queue_row(b: Bundle, s: dict) -> dict:
    probs = b.effective(s["id"])
    focus = focus_problem(probs) if probs else None
    finals = b.problem_finals(s["id"]) if probs else {}
    chips = queue_chips(probs, error_label) if probs else []
    if s.get("quality") and not s["quality"].get("ok") and "Retake suggested" not in chips:
        chips.append("Retake suggested")
    pos = next((p["position"] for p in b.problems if focus and p["id"] == focus["problem_id"]), None)
    return {
        "submission_id": s["id"],
        "student_id": s["student_id"],
        "status": s["status"],
        "focus_problem_id": focus["problem_id"] if focus else None,
        "focus_problem_order": pos,
        "score": finals.get(focus["problem_id"]) if focus else None,
        "score_max": float(focus["max_score"]) if focus else 0,
        "confidence": paper_confidence(probs) if probs else None,
        "chips": chips,
    }


def next_in_queue(b: Bundle, after_sub_id: str) -> dict | None:
    pending = [s for s in b.subs if s["status"] in ("needs_review", "failed", "ready") and s["id"] != after_sub_id]
    if not pending:
        return None
    rows = sorted((queue_row(b, s) for s in pending), key=lambda r: (r["status"] == "ready", r["confidence"] or 0, r["student_id"]))
    return {"id": rows[0]["submission_id"], "student_id": rows[0]["student_id"]}


# ---------------------------------------------------------------- submission detail / review / approve
def _review_row(store: Store, sub_id: str) -> dict:
    r = store.one("teacher_reviews", submission_id=sub_id)
    if r:
        return r
    ts = now_iso()
    r = {
        "id": f"rev-{sub_id}",
        "submission_id": sub_id,
        "final_score": None,
        "unit_edits": {},
        "problem_scores": {},
        "feedback": {},
        "edit_log": [],
        "approved": False,
        "approved_at": None,
        "created_at": ts,
        "updated_at": ts,
    }
    store.insert("teacher_reviews", r)
    return r


def submission_detail(store: Store, sub_id: str) -> dict:
    s = store.get("submissions", sub_id)
    if not s:
        raise NotFound("Paper not found.")
    b = Bundle(store, s["activity_id"])
    ai = b.ai.get(sub_id)
    review = b.reviews.get(sub_id) or {
        "unit_edits": {},
        "problem_scores": {},
        "feedback": {},
        "edit_log": [],
        "final_score": None,
        "approved": False,
        "approved_at": None,
        "updated_at": None,
    }
    probs = b.effective(sub_id)
    feedback = dict(review.get("feedback") or {})
    for p in probs:
        feedback.setdefault(p["problem_id"], p.get("student_hint") or "")
    focus = focus_problem(probs) if probs else None
    return {
        "id": s["id"],
        "student_id": s["student_id"],
        "status": s["status"],
        "image_url": store.signed_url(s["image_path"]) if s.get("image_path") else None,
        "image_deleted": not s.get("image_path"),
        "activity": activity_full(b),
        "ai_result": None
        if not ai
        else {
            "problems": probs,
            "suggested_score": ai["suggested_score"],
            "max_score": float(ai["max_score"]),
            "overall_confidence": float(ai["overall_confidence"]),
            "flags": ai.get("flags") or [],
            "model": ai["model"],
            "prompt_version": ai["prompt_version"],
            "created_at": ai["created_at"],
            "failure_reason": (ai.get("raw_json") or {}).get("error") if "grading_failed" in (ai.get("flags") or []) else None,
        },
        "review": {
            "unit_edits": review.get("unit_edits") or {},
            "problem_scores": review.get("problem_scores") or {},
            "feedback": feedback,
            "edit_log": review.get("edit_log") or [],
            "final_score": review.get("final_score"),
            "approved": bool(review.get("approved")),
            "approved_at": review.get("approved_at"),
            "updated_at": review.get("updated_at"),
        },
        "next_submission": next_in_queue(b, sub_id),
        "focus_problem_id": focus["problem_id"] if focus else None,
    }


def patch_review(store: Store, sub_id: str, unit_edits: dict | None, problem_scores: dict | None, feedback: dict | None) -> dict:
    s = store.get("submissions", sub_id)
    if not s:
        raise NotFound("Paper not found.")
    b = Bundle(store, s["activity_id"])
    if sub_id not in b.ai:
        raise Conflict("This paper has not been graded yet.")
    r = _review_row(store, sub_id)
    ts = now_iso()
    log = list(r.get("edit_log") or [])
    ue = dict(r.get("unit_edits") or {})
    ps = dict(r.get("problem_scores") or {})
    fb = dict(r.get("feedback") or {})
    valid_problems = {p["id"] for p in b.problems}
    max_by_problem = {p["problem_id"]: float(p["max_score"]) for p in b.ai[sub_id]["problem_results"]}
    allowed_types = set(ERROR_TYPES[b.subject])
    for key, edit in (unit_edits or {}).items():
        pid = key.rsplit(":", 1)[0]
        if pid not in valid_problems:
            raise Conflict(f"Unknown unit '{key}'.")
        clean = {}
        for k, v in edit.items():
            if k == "points_awarded":
                v = max(0.0, float(v))
            elif k == "verdict" and v not in ("correct", "error", "unclear"):
                raise Conflict(f"Invalid verdict '{v}'.")
            elif k == "error_type" and v not in (None, *allowed_types):
                raise Conflict(f"Invalid error type '{v}'.")
            elif k not in ("transcribed_text", "comment", "points_awarded", "verdict", "error_type"):
                continue
            prev = (ue.get(key) or {}).get(k)
            if prev != v:
                log.append({"at": ts, "field": f"unit.{key}.{k}", "from": prev, "to": v})
            clean[k] = v
        ue[key] = {**(ue.get(key) or {}), **clean}
    for pid, v in (problem_scores or {}).items():
        if pid not in valid_problems:
            raise Conflict(f"Unknown problem '{pid}'.")
        if v is not None:
            v = float(v)
            if v < 0 or v > max_by_problem.get(pid, 0):
                raise Conflict(f"Score must be between 0 and {max_by_problem.get(pid, 0):g}.")
        if ps.get(pid) != v:
            log.append({"at": ts, "field": f"problem_scores.{pid}", "from": ps.get(pid), "to": v})
        if v is None:
            ps.pop(pid, None)
        else:
            ps[pid] = v
    for pid, text in (feedback or {}).items():
        if pid not in valid_problems:
            raise Conflict(f"Unknown problem '{pid}'.")
        if fb.get(pid) != text:
            log.append({"at": ts, "field": f"feedback.{pid}", "from": fb.get(pid), "to": text})
        fb[pid] = text
    patch = {"unit_edits": ue, "problem_scores": ps, "feedback": fb, "edit_log": log, "updated_at": ts}
    store.update("teacher_reviews", r["id"], patch)
    if s["status"] == "approved":
        b2 = Bundle(store, s["activity_id"])
        store.update("teacher_reviews", r["id"], {"final_score": b2.final_total(sub_id)})
    return submission_detail(store, sub_id)


def approve(store: Store, sub_id: str) -> dict:
    s = store.get("submissions", sub_id)
    if not s:
        raise NotFound("Paper not found.")
    b = Bundle(store, s["activity_id"])
    if sub_id not in b.ai:
        raise Conflict("This paper has not been graded yet.")
    r = _review_row(store, sub_id)
    b.reviews[sub_id] = r
    total = b.final_total(sub_id)
    ts = now_iso()
    feedback = dict(r.get("feedback") or {})
    for p in b.effective(sub_id):
        feedback.setdefault(p["problem_id"], p.get("student_hint") or "")
    log = list(r.get("edit_log") or []) + [{"at": ts, "field": "approved", "from": False, "to": True}]
    store.update("teacher_reviews", r["id"], {"approved": True, "approved_at": ts, "final_score": total, "feedback": feedback, "edit_log": log, "updated_at": ts})
    patch: dict = {"status": "approved", "updated_at": ts}
    if get_settings().delete_images_on_approve and s.get("image_path"):
        store.delete_image(s["image_path"])
        patch["image_path"] = None
    store.update("submissions", sub_id, patch)
    touch(store, s["activity_id"])
    return {"submission": submission_detail(store, sub_id), "final_score": total, "max_score": float(b.activity["total_points"])}


# ---------------------------------------------------------------- class summary
def _error_units(b: Bundle) -> list[tuple[str, str, str, dict]]:
    """(sub_id, student_id, problem_id, unit) for every error unit with an error type, edits applied."""
    out = []
    for s in b.subs:
        if s["status"] not in ("needs_review", "ready", "approved"):
            continue
        for p in b.effective(s["id"]):
            for u in p["units"]:
                if u.get("verdict") == "error" and u.get("error_type"):
                    out.append((s["id"], s["student_id"], p["problem_id"], u))
    return out


def class_summary(store: Store, activity_id: str) -> dict:
    from . import ai_text

    b = Bundle(store, activity_id)
    roster = b.students()
    approved = [s for s in b.subs if s["status"] == "approved"]
    graded = [s for s in b.subs if s["status"] in ("needs_review", "ready", "approved")]
    errs = _error_units(b)
    by_type = {k: 0 for k in ERROR_TYPES[b.subject]}
    by_crit: dict[str, int] = {}
    for _sid, _st, _pid, u in errs:
        by_type[u["error_type"]] = by_type.get(u["error_type"], 0) + 1
        by_crit[u["criterion"]] = by_crit.get(u["criterion"], 0) + 1
    basis = approved or graded
    per_problem = []
    for p in b.problems:
        vals = [b.problem_finals(s["id"]).get(p["id"]) for s in basis]
        vals = [v for v in vals if v is not None]
        per_problem.append({"label": f"{PROBLEM_PREFIX[b.subject]}{p['position']}", "average": _r1(sum(vals) / len(vals)) if vals else 0})
    avg, out_of = class_average(b)
    most = max(by_crit.items(), key=lambda kv: kv[1])[0] if by_crit else None

    keys = {f"{sid}:{pid}:{u['index']}": (st, pid, u) for sid, st, pid, u in errs}
    signature = hashlib.sha1(json.dumps(sorted(keys)).encode()).hexdigest()
    cached = store.get("class_summaries", activity_id)
    ai_model = cached["model"] if cached else None
    if errs and (not cached or (cached["signature"] not in ("seed", signature))):
        fresh = ai_text.misconceptions(b, keys)
        if fresh:
            row = {"id": activity_id, "activity_id": activity_id, "signature": signature, **fresh, "created_at": now_iso()}
            store.insert("class_summaries", row)
            cached, ai_model = row, row["model"]
    clusters = []
    if cached:
        for m in cached["misconceptions"]:
            members = [keys[i] for i in m.get("ids", []) if i in keys]
            students = {st for st, _pid, _u in members}
            if not students:
                continue
            probs = sorted({pid for _st, pid, _u in members}, key=lambda pid: next((p["position"] for p in b.problems if p["id"] == pid), 0))
            clusters.append({"text": m["label"], "error_type": m["error_type"], "count": len(students), "problems": [b.problem_label(pid) for pid in probs]})
    else:
        # Fallback without an LLM: group by error type (counts still from code).
        for et, n in sorted(by_type.items(), key=lambda kv: -kv[1])[:2]:
            if not n:
                continue
            members = [(st, pid) for _sid, st, pid, u in errs if u["error_type"] == et]
            probs = sorted({pid for _st, pid in members})
            clusters.append({"text": f"made {error_label(et).lower()} errors", "error_type": et, "count": len({st for st, _ in members}), "problems": [b.problem_label(pid) for pid in probs]})
    clusters.sort(key=lambda c: -c["count"])
    return {
        "activity": activity_summary(b),
        "approved": len(approved),
        "students": len(roster) or len(b.subs),
        "average_score": round(avg) if avg else 0,
        "out_of": out_of,
        "most_missed_criterion": most,
        "errors_by_type": [{"error_type": k, "label": error_label(k), "count": v} for k, v in by_type.items()],
        "per_problem": per_problem,
        "misconceptions": clusters,
        "reteach_focus": cached["reteach_focus"] if cached else "Grade and review more papers to get a suggested reteach focus.",
        "ai_model": ai_model,
    }


# ---------------------------------------------------------------- gradebook
def gradebook(store: Store, activity_id: str) -> dict:
    b = Bundle(store, activity_id)
    by_student = {s["student_id"]: s for s in b.subs}
    recent = datetime.now(timezone.utc) - timedelta(minutes=15)
    rows = []
    for st in b.students():
        s = by_student.get(st)
        if s and s["status"] == "approved":
            finals = b.problem_finals(s["id"])
            rev = b.reviews.get(s["id"]) or {}
            edits = rev.get("unit_edits") or {}
            overrides = rev.get("problem_scores") or {}
            scores = [finals.get(p["id"]) for p in b.problems]
            edited = [p["id"] in overrides or any(k.startswith(p["id"] + ":") for k in edits) for p in b.problems]
            just = (d := _dt(rev.get("approved_at"))) is not None and d >= recent
            rows.append({"student_id": st, "submission_id": s["id"], "scores": scores, "edited": edited, "total": round(sum(v or 0 for v in scores), 2), "just_approved": just})
        else:
            rows.append({"student_id": st, "submission_id": s["id"] if s else None, "scores": [None] * len(b.problems), "edited": [False] * len(b.problems), "total": None, "just_approved": False})
    rows.sort(key=lambda r: (not r["just_approved"], r["student_id"]))
    return {"activity": activity_summary(b), "columns": [f"{PROBLEM_PREFIX[b.subject]}{p['position']}" for p in b.problems], "rows": rows}


def approved_grades(store: Store, activity_id: str) -> list[dict]:
    b = Bundle(store, activity_id)
    out = []
    for s in b.subs:
        if s["status"] != "approved":
            continue
        rev = b.reviews.get(s["id"]) or {}
        out.append({"student_ref": s["student_id"], "score": b.final_total(s["id"]), "max_score": float(b.activity["total_points"]), "approved_at": rev.get("approved_at")})
    return out

