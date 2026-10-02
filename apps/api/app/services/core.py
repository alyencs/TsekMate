"""Business logic shared by the API routes. Everything a teacher sees is computed here from stored rows."""
from __future__ import annotations

import hashlib
import json
import math
import os
import threading
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from ..grading.flags import error_label
from ..grading.scoring import apply_edits, clean_problem, focus_problem, paper_confidence, queue_chips, rubric_problems, spread_score
from ..models import ERROR_TYPES, ActivityIn
from ..store.base import Store, UniqueViolation, new_id, now_iso


class NotFound(Exception):
    pass


class Conflict(Exception):
    pass


TZ = ZoneInfo(os.getenv("APP_TIMEZONE", "Asia/Manila"))
GRADED = ("needs_review", "ready", "approved", "failed")
BUSY = "This paper is being checked right now. Try again when grading finishes."
# Serializes every write that gives a paper a student (upload, teacher assignment, AI identity matching), so two
# papers can never claim one student. The store's unique rule (database index) is the second line of defense.
assignment_lock = threading.Lock()
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
        # The rubric's declared total; older rows without one fall back to the criteria sum.
        self.rubric_total = float(r["total_points"]) if r and r.get("total_points") is not None else round(sum(float(c["points"]) for c in self.rubric), 2)
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
        """Problem results scored against THIS activity's rubric, with the teacher's edits applied.

        - unit edits (transcription, verdict, error type, comment) are overlaid and the criteria recomputed;
        - teacher criterion scores (`criterion_scores`, key "problem_id::criterion") replace the computed points;
        - `criteria_scores` always lists every rubric criterion; `final_score` is their sum (the only total used
          by review, approval, gradebook, and class summary).
        """
        ai = self.ai.get(sub_id)
        if not ai:
            return []
        rev = self.reviews.get(sub_id) or {}
        edits = rev.get("unit_edits") or {}
        overrides = dict(rev.get("criterion_scores") or {})
        legacy = rev.get("problem_scores") or {}  # per-problem overrides saved before migration 003
        out = []
        for p in ai["problem_results"]:
            e = apply_edits(p, edits, self.rubric) if p.get("units") else clean_problem({**p, "units": []}, self.rubric)
            pid = p["problem_id"]
            if legacy.get(pid) is not None and not any(k.startswith(pid + "::") for k in overrides):
                overrides.update(spread_score(pid, e["criteria_scores"], legacy[pid]))
            e["ai_suggested_score"] = clean_problem(p, self.rubric)["suggested_score"] if p.get("units") else 0.0
            for c in e["criteria_scores"]:
                c["computed"] = c["awarded"]
                v = overrides.get(f"{p['problem_id']}::{c['name']}")
                c["edited"] = v is not None
                if v is not None:
                    c["awarded"] = round(min(max(float(v), 0.0), c["points"]), 2)
            e["final_score"] = round(sum(c["awarded"] for c in e["criteria_scores"]), 2)
            e["max_score"] = round(sum(c["points"] for c in e["criteria_scores"]), 2)
            out.append(e)
        return out

    def problem_finals(self, sub_id: str) -> dict[str, float]:
        return {p["problem_id"]: float(p["final_score"]) for p in self.effective(sub_id)}

    def final_total(self, sub_id: str) -> float:
        return round(sum(self.problem_finals(sub_id).values()), 2)

    def students(self) -> list[str]:
        return [s["id"] for s in self.roster()]

    def roster(self) -> list[dict]:
        """Enrolled students: everyone whose section equals the activity's class."""
        if not hasattr(self, "_roster"):
            rows = self.store.select("students", section=self.activity["class_name"])
            self._roster = sorted(({"id": r["id"], "name": r.get("name") or ""} for r in rows), key=lambda r: r["id"])
        return self._roster

    def student_name(self, student_id: str | None) -> str | None:
        if not student_id:
            return None
        return next((r["name"] for r in self.roster() if r["id"] == student_id), None) or None

    def taken(self) -> dict[str, str]:
        return {s["student_id"]: s["id"] for s in self.subs if s.get("student_id")}

    def problem_label(self, problem_id: str) -> str:
        p = next((p for p in self.problems if p["id"] == problem_id), None)
        if not p:
            return problem_id
        return f"Item {p['position']}" if self.subject == "grammar" else f"P{p['position']}"


def activity_summary(b: Bundle) -> dict:
    a = b.activity
    st = [s["status"] for s in b.subs]
    roster = b.roster()
    taken = b.taken()
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
        "roster_size": len(roster),
        "not_submitted": sum(1 for r in roster if r["id"] not in taken),
        "unidentified": sum(1 for x in b.subs if not x.get("student_id")),
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
        "rubric_total": b.rubric_total,
        "rubric_errors": rubric_problems(b.rubric, b.rubric_total),
        "rubric_locked": any(x["status"] in GRADED + ("grading",) for x in b.subs),
    }


def list_activities(store: Store) -> list[dict]:
    out = [activity_summary(Bundle(store, a["id"])) for a in store.select("activities")]
    return sorted(out, key=lambda a: a["updated_at"], reverse=True)


def create_activity(store: Store, data: ActivityIn) -> dict:
    errs = rubric_problems([c.model_dump() for c in data.rubric], data.rubric_total)
    if errs:
        raise Conflict(" ".join(errs))
    aid = f"act-{new_id()[:8]}"
    total = float(data.rubric_total) * len(data.problems)
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
    store.insert("rubrics", {"id": f"{aid}-rubric", "activity_id": aid, "criteria": _clean_criteria([c.model_dump() for c in data.rubric]), "total_points": float(data.rubric_total)})
    return activity_full(Bundle(store, aid))


def _clean_criteria(criteria: list[dict]) -> list[dict]:
    return [{"name": str(c["name"]).strip(), "description": str(c.get("description") or "").strip(), "points": float(c["points"])} for c in criteria]


def update_rubric(store: Store, activity_id: str, criteria: list[dict], total: float) -> dict:
    """Replace an activity's rubric before any paper is graded (so every result uses one rubric)."""
    b = Bundle(store, activity_id)
    if any(x["status"] in GRADED + ("grading",) for x in b.subs):
        raise Conflict("This activity already has graded papers, so its rubric can't change. Create a new activity for a different rubric.")
    errs = rubric_problems(criteria, total)
    if errs:
        raise Conflict(" ".join(errs))
    row = store.one("rubrics", activity_id=activity_id)
    rid = row["id"] if row else f"{activity_id}-rubric"
    store.insert("rubrics", {"id": rid, "activity_id": activity_id, "criteria": _clean_criteria(criteria), "total_points": float(total)})
    store.update("activities", activity_id, {"total_points": float(total) * len(b.problems), "updated_at": now_iso()})
    return activity_full(Bundle(store, activity_id))


def touch(store: Store, activity_id: str) -> None:
    store.update("activities", activity_id, {"updated_at": now_iso()})


# ---------------------------------------------------------------- dashboard
def dashboard(store: Store, now: datetime | None = None) -> dict:
    acts = list_activities(store)
    badge = sum(a["flagged"] for a in acts)
    now = now or datetime.now(timezone.utc)
    now_local = now.astimezone(TZ)
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
    day_ago = now - timedelta(hours=24)
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
    for s in sorted(b.subs, key=lambda s: (s.get("student_id") is None, s.get("student_id") or "", s["created_at"])):
        out.append(
            {
                "id": s["id"],
                "student_id": s.get("student_id"),
                "student_name": b.student_name(s.get("student_id")),
                "status": s["status"],
                "image_url": store.signed_url(s["image_path"]) if s.get("image_path") else None,
                "quality": s.get("quality"),
            }
        )
    return out


def add_uploads(store: Store, activity_id: str, files: list[tuple[str, bytes, str]], student_ids: list[str] | None = None) -> list[dict]:
    """Store new papers. `files` are (name, bytes, content type) already checked by services.uploads.validate.

    The whole request is refused (nothing stored) when a student would get two papers, or when the same photo is
    uploaded twice (a double-click or a repeated request), so a retry can never create duplicates."""
    from .quality import check
    from .uploads import EXTENSIONS

    hashes = [hashlib.sha256(data).hexdigest() for _n, data, _c in files]
    seen: dict[str, str] = {}
    for (name, _d, _c), h in zip(files, hashes):
        if h in seen:
            raise Conflict(f"{name} is the same photo as {seen[h]}. Upload each paper once.")
        seen[h] = name
    with assignment_lock:
        b = Bundle(store, activity_id)
        taken = set(b.taken())
        roster = b.students()
        existing = {s.get("image_hash") for s in b.subs if s.get("image_hash")}
        again = [name for (name, _d, _c), h in zip(files, hashes) if h in existing]
        if again:
            raise Conflict(f"Already uploaded to this activity: {', '.join(again)}. Delete the earlier copy first to upload it again.")
        ids: list[str | None]
        if student_ids:
            bad = [s for s in student_ids if s not in roster]
            if bad:
                raise Conflict(f"Unknown student ID(s) for {b.activity['class_name']}: {', '.join(bad)}")
            twice = sorted({s for s in student_ids if student_ids.count(s) > 1})
            if twice:
                raise Conflict(f"{', '.join(twice)} is listed for more than one file. Each student gets one paper per activity.")
            dup = [s for s in student_ids if s in taken]
            if dup:
                raise Conflict(f"{', '.join(dup)} already has a paper for this activity. Delete it first to upload a retake.")
            ids = list(student_ids)
        else:
            # Papers start unidentified; the grading call reads the name / ID on the paper and matches the roster.
            ids = [None] * len(files)
        created = []
        for (name, data, ctype), sid, h in zip(files, ids, hashes):
            sub_id = f"sub-{new_id()[:12]}"
            path = f"uploads/{activity_id}/{sub_id}.{EXTENSIONS[ctype]}"
            q = check(data) if ctype.startswith("image/") else {"ok": True, "reason": None}
            ts = now_iso()
            row = {
                "id": sub_id,
                "activity_id": activity_id,
                "student_id": sid,
                "identity": {"status": "manual", "method": "teacher_upload"} if sid else {"status": "pending"},
                "image_path": path,
                "image_hash": h,
                "status": "uploaded",
                "quality": q,
                "created_at": ts,
                "updated_at": ts,
            }
            try:
                store.insert("submissions", row)
            except UniqueViolation:
                raise Conflict(f"{sid} already has a paper for this activity. Delete it first to upload a retake.") from None
            try:
                store.put_image(path, data, ctype)
            except Exception:
                store.delete("submissions", id=sub_id)  # never leave a paper row without its photo
                raise
            created.append({"id": sub_id, "student_id": sid, "student_name": b.student_name(sid), "status": "uploaded", "image_url": store.signed_url(path), "quality": q})
    touch(store, activity_id)
    from . import notifications

    notifications.add(
        store, "upload_done", f"{len(created)} paper{'s' if len(created) != 1 else ''} uploaded",
        f"{b.activity['title']}. Ready to grade.", link=f"/activities/{activity_id}/upload", activity_id=activity_id,
    )
    return created


def delete_submission(store: Store, sub_id: str) -> None:
    s = store.get("submissions", sub_id)
    if not s:
        raise NotFound("Paper not found.")
    if s["status"] == "approved":
        raise Conflict("This paper is already approved and in the gradebook, so it cannot be deleted here.")
    if s["status"] == "grading":
        raise Conflict(BUSY)
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
    rows.sort(key=lambda r: (r["confidence"] if r["confidence"] is not None else -1, r["student_id"] or "~"))
    return {"activity": activity_summary(b), "counts": counts, "rows": rows}


def queue_row(b: Bundle, s: dict) -> dict:
    probs = b.effective(s["id"])
    focus = focus_problem(probs) if probs else None
    finals = b.problem_finals(s["id"]) if probs else {}
    chips = queue_chips(probs, error_label) if probs else []
    if s.get("quality") and not s["quality"].get("ok") and "Retake suggested" not in chips:
        chips.append("Retake suggested")
    if not s.get("student_id") and s["status"] in GRADED:
        chips.insert(0, "Student not identified")
    pos = next((p["position"] for p in b.problems if focus and p["id"] == focus["problem_id"]), None)
    return {
        "submission_id": s["id"],
        "student_id": s.get("student_id"),
        "student_name": b.student_name(s.get("student_id")),
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
    rows = sorted((queue_row(b, s) for s in pending), key=lambda r: (r["status"] == "ready", r["confidence"] or 0, r["student_id"] or "~"))
    return {"id": rows[0]["submission_id"], "student_id": rows[0]["student_id"], "student_name": rows[0]["student_name"]}


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
        "criterion_scores": {},
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
        "criterion_scores": {},
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
        "student_id": s.get("student_id"),
        "student_name": b.student_name(s.get("student_id")),
        "identity": s.get("identity") or {},
        "roster": [{**r, "has_paper": r["id"] in b.taken() and b.taken()[r["id"]] != s["id"]} for r in b.roster()],
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
            "created_at": ai["created_at"],
            # Teacher-facing reason only; the technical reason, model, and prompt version stay in the database.
            "failure_reason": ((ai.get("raw_json") or {}).get("teacher_message") or "AI grading didn't finish for this paper.")
            if "grading_failed" in (ai.get("flags") or []) else None,
        },
        "review": {
            "unit_edits": review.get("unit_edits") or {},
            "criterion_scores": review.get("criterion_scores") or {},
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


def patch_review(store: Store, sub_id: str, unit_edits: dict | None, criterion_scores: dict | None, feedback: dict | None) -> dict:
    s = store.get("submissions", sub_id)
    if not s:
        raise NotFound("Paper not found.")
    if s["status"] == "grading":
        raise Conflict(BUSY)
    b = Bundle(store, s["activity_id"])
    if sub_id not in b.ai:
        raise Conflict("This paper has not been graded yet.")
    r = _review_row(store, sub_id)
    ts = now_iso()
    log = list(r.get("edit_log") or [])
    first_new = len(log)
    ue = dict(r.get("unit_edits") or {})
    cs = dict(r.get("criterion_scores") or {})
    if r.get("problem_scores"):  # carry legacy per-problem overrides over as criterion scores on the first edit
        b.reviews[sub_id] = r
        for e in b.effective(sub_id):
            for c in e["criteria_scores"]:
                if c["edited"]:
                    cs.setdefault(f"{e['problem_id']}::{c['name']}", c["awarded"])
    fb = dict(r.get("feedback") or {})
    valid_problems = {p["id"] for p in b.problems}
    crit_max = {c["name"]: float(c["points"]) for c in b.rubric}
    allowed_types = set(ERROR_TYPES[b.subject])
    for key, edit in (unit_edits or {}).items():
        pid = key.rsplit(":", 1)[0]
        if pid not in valid_problems:
            raise Conflict(f"Unknown unit '{key}'.")
        clean = {}
        # `edit` is a validated models.UnitEdit dump: only known fields, finite non-negative points, real strings.
        for k, v in edit.items():
            if k == "points_awarded":
                v = float(v)
                if not math.isfinite(v) or v < 0:
                    raise Conflict("Points must be a number of 0 or more.")
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
    for key, v in (criterion_scores or {}).items():
        pid, _, name = key.partition("::")
        if pid not in valid_problems:
            raise Conflict(f"Unknown problem '{pid}'.")
        if name not in crit_max:
            raise Conflict(f"'{name}' is not a criterion in this activity's rubric.")
        if v is not None:
            v = float(v)
            if not math.isfinite(v) or v < 0 or v > crit_max[name]:
                raise Conflict(f"{name}: enter a score from 0 to {crit_max[name]:g}.")
        if cs.get(key) != v:
            log.append({"at": ts, "field": f"criterion.{key}", "from": cs.get(key), "to": v})
        if v is None:
            cs.pop(key, None)
        else:
            cs[key] = v
    for pid, text in (feedback or {}).items():
        if pid not in valid_problems:
            raise Conflict(f"Unknown problem '{pid}'.")
        if fb.get(pid) != text:
            log.append({"at": ts, "field": f"feedback.{pid}", "from": fb.get(pid), "to": text})
        fb[pid] = text
    changed = len(log) > first_new
    patch = {"unit_edits": ue, "criterion_scores": cs, "feedback": fb, "edit_log": log, "updated_at": ts}
    if r.get("problem_scores"):
        patch["problem_scores"] = {}
    if s["status"] == "approved" and changed:
        # An approved grade never changes silently: a real edit withdraws the approval, the paper goes back to the
        # review queue, and the gradebook leaves it out until the teacher approves again.
        b.reviews[sub_id] = {**r, **patch}
        from ..grading.scoring import needs_teacher

        back = "needs_review" if needs_teacher(b.effective(sub_id)) or not s.get("student_id") else "ready"
        if not store.update_where("submissions", sub_id, {"status": back, "updated_at": ts}, status="approved"):
            raise Conflict("This paper changed while you were editing it. Reload the page and try again.")
        log.append({"at": ts, "field": "approved", "from": True, "to": False})
        patch.update({"approved": False, "final_score": None})
        touch(store, s["activity_id"])
    store.update("teacher_reviews", r["id"], patch)
    return submission_detail(store, sub_id)


def approve(store: Store, sub_id: str) -> dict:
    s = store.get("submissions", sub_id)
    if not s:
        raise NotFound("Paper not found.")
    if s["status"] not in ("needs_review", "ready", "failed", "approved"):
        raise Conflict(BUSY if s["status"] == "grading" else "This paper has not been graded yet.")
    b = Bundle(store, s["activity_id"])
    if sub_id not in b.ai:
        raise Conflict("This paper has not been graded yet.")
    if not s.get("student_id"):
        raise Conflict("Choose the student for this paper before approving (Student: Not identified).")
    r = _review_row(store, sub_id)
    b.reviews[sub_id] = r
    total = b.final_total(sub_id)
    ts = now_iso()
    patch: dict = {"status": "approved", "updated_at": ts}
    from . import settings as app_settings

    delete_image = bool(app_settings.get(store)["delete_images_on_approve"] and s.get("image_path"))
    if delete_image:
        patch["image_path"] = None
    # Compare-and-set on the status read above: if Grade again (or anything else) changed the paper in between,
    # nothing is written and the teacher is told, so the paper never ends up both approved and re-graded.
    if not store.update_where("submissions", sub_id, patch, status=s["status"], student_id=s["student_id"]):
        raise Conflict("This paper changed while you were approving it. Reload the page and check it again.")
    feedback = dict(r.get("feedback") or {})
    for p in b.effective(sub_id):
        feedback.setdefault(p["problem_id"], p.get("student_hint") or "")
    log = list(r.get("edit_log") or []) + [{"at": ts, "field": "approved", "from": False, "to": True}]
    store.update("teacher_reviews", r["id"], {"approved": True, "approved_at": ts, "final_score": total, "feedback": feedback, "edit_log": log, "updated_at": ts})
    if delete_image:
        store.delete_image(s["image_path"])
    touch(store, s["activity_id"])
    return {"submission": submission_detail(store, sub_id), "final_score": total, "max_score": float(b.activity["total_points"])}


def assign_student(store: Store, sub_id: str, student_id: str) -> dict:
    """Teacher associates a paper with a student on the class roster (for unidentified or mismatched papers)."""
    with assignment_lock:
        s = store.get("submissions", sub_id)
        if not s:
            raise NotFound("Paper not found.")
        if s["status"] == "grading":
            raise Conflict(BUSY)
        b = Bundle(store, s["activity_id"])
        student = next((r for r in b.roster() if r["id"] == student_id), None)
        if not student:
            raise Conflict(f"{student_id} is not on the roster of {b.activity['class_name']}.")
        other = b.taken().get(student_id)
        if other and other != sub_id:
            raise Conflict(f"{student['name']} ({student_id}) already has a paper for this activity. Delete or reassign that paper first.")
        if s["status"] == "approved" and s.get("student_id") != student_id:
            raise Conflict("This paper is already approved. Its student cannot be changed here.")
        ts = now_iso()
        identity = {**(s.get("identity") or {}), "status": "matched", "method": "teacher", "previous_student_id": s.get("student_id"), "assigned_at": ts}
        patch: dict = {"student_id": student_id, "identity": identity, "updated_at": ts}
        if s["status"] == "needs_review" and sub_id in b.ai:
            from ..grading.scoring import needs_teacher

            if not needs_teacher(b.effective(sub_id)):
                patch["status"] = "ready"  # it was only waiting for the student to be identified
        try:
            ok = store.update_where("submissions", sub_id, patch, status=s["status"], student_id=s.get("student_id"))
        except UniqueViolation:
            raise Conflict(f"{student['name']} ({student_id}) already has a paper for this activity. Delete or reassign that paper first.") from None
        if not ok:
            raise Conflict("This paper changed in the meantime. Reload the page and try again.")
    r = _review_row(store, sub_id)
    store.update("teacher_reviews", r["id"], {"edit_log": list(r.get("edit_log") or []) + [{"at": ts, "field": "student_id", "from": s.get("student_id"), "to": student_id}], "updated_at": ts})
    touch(store, s["activity_id"])
    return submission_detail(store, sub_id)


ROSTER_STATUS = {
    "uploaded": "Submitted",
    "grading": "Checking",
    "failed": "Grading failed",
    "needs_review": "Needs review",
    "ready": "Ready to approve",
    "approved": "Approved",
}


def roster_status(b: Bundle) -> list[dict]:
    """One row per enrolled student: did they submit, and where is the paper in the workflow."""
    by_student = {s["student_id"]: s for s in b.subs if s.get("student_id")}
    out = []
    for r in b.roster():
        sub = by_student.get(r["id"])
        out.append({"student_id": r["id"], "student_name": r["name"], "submission_id": sub["id"] if sub else None,
                    "status": ROSTER_STATUS.get(sub["status"], sub["status"]) if sub else "Not submitted"})
    return out


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
                    out.append((s["id"], s.get("student_id") or s["id"], p["problem_id"], u))
    return out


def _error_keys(errs: list[tuple[str, str, str, dict]]) -> dict[str, tuple]:
    """'sub_id:problem_id:unit_index' -> (student, problem_id, unit). The ids the misconception clusters refer to."""
    return {f"{sid}:{pid}:{u['index']}": (st, pid, u) for sid, st, pid, u in errs}


def _signature(keys: dict) -> str:
    return hashlib.sha1(json.dumps(sorted(f"{k}:{u.get('error_type')}" for k, (_st, _pid, u) in keys.items())).encode()).hexdigest()


def error_signature(b: Bundle) -> str:
    """Fingerprint of the class's current error units (which paper, problem, unit, and error type)."""
    return _signature(_error_keys(_error_units(b)))


def class_summary(store: Store, activity_id: str, refresh: bool = False) -> dict:
    """Counts always come from code. The AI part (misconception names, reteach focus) is read from the cache; it is
    generated only when the teacher asks for it (`refresh=True`, POST .../class-summary/refresh), so opening the page
    never makes a paid AI call. `ai_summary.stale` says whether the cached names predate the current errors."""
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

    keys = _error_keys(errs)
    signature = _signature(keys)
    cached = store.get("class_summaries", activity_id)
    refresh_failed = False
    if refresh and errs:
        fresh = ai_text.misconceptions(b, keys)
        if fresh:
            row = {"id": activity_id, "activity_id": activity_id, "signature": signature, **fresh, "created_at": now_iso()}
            store.insert("class_summaries", row)
            cached = row
        else:
            refresh_failed = True
    stale = bool(errs) and (not cached or cached["signature"] != signature)
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
    rs = roster_status(b)
    return {
        "activity": activity_summary(b),
        "approved": len(approved),
        "students": len(roster) or len(b.subs),
        "submissions": {
            "submitted": sum(1 for r in rs if r["status"] != "Not submitted"),
            "not_submitted": [r for r in rs if r["status"] == "Not submitted"],
            "unidentified": sum(1 for x in b.subs if not x.get("student_id")),
        },
        "average_score": round(avg) if avg else 0,
        "out_of": out_of,
        "most_missed_criterion": most,
        "errors_by_type": [{"error_type": k, "label": error_label(k), "count": v} for k, v in by_type.items()],
        "per_problem": per_problem,
        "misconceptions": clusters,
        "reteach_focus": cached["reteach_focus"] if cached else "Grade and review more papers to get a suggested reteach focus.",
        "ai_summary": {"cached": bool(cached), "stale": stale, "refresh_failed": refresh_failed, "created_at": cached.get("created_at") if cached else None},
    }


# ---------------------------------------------------------------- gradebook
def gradebook(store: Store, activity_id: str) -> dict:
    b = Bundle(store, activity_id)
    by_student = {s["student_id"]: s for s in b.subs if s.get("student_id")}
    recent = datetime.now(timezone.utc) - timedelta(minutes=15)
    rows = []
    status = {r["student_id"]: r["status"] for r in roster_status(b)}
    names = {r["id"]: r["name"] for r in b.roster()}
    for st in b.students():
        s = by_student.get(st)
        if s and s["status"] == "approved":
            finals = b.problem_finals(s["id"])
            rev = b.reviews.get(s["id"]) or {}
            edits = rev.get("unit_edits") or {}
            overrides = rev.get("criterion_scores") or {}
            scores = [finals.get(p["id"]) for p in b.problems]
            legacy = rev.get("problem_scores") or {}
            edited = [p["id"] in legacy or any(k.startswith(p["id"] + "::") for k in overrides) or any(k.startswith(p["id"] + ":") for k in edits) for p in b.problems]
            just = (d := _dt(rev.get("approved_at"))) is not None and d >= recent
            rows.append({"student_id": st, "student_name": names[st], "status": status[st], "submission_id": s["id"], "scores": scores, "edited": edited, "total": round(sum(v or 0 for v in scores), 2), "just_approved": just})
        else:
            rows.append({"student_id": st, "student_name": names[st], "status": status[st], "submission_id": s["id"] if s else None, "scores": [None] * len(b.problems), "edited": [False] * len(b.problems), "total": None, "just_approved": False})
    rows.sort(key=lambda r: (not r["just_approved"], r["student_id"]))
    roster_ids = set(names)
    for s in b.subs:  # approved papers of students who are no longer on this class roster stay visible
        st = s.get("student_id")
        if st and st not in roster_ids and s["status"] == "approved":
            finals = b.problem_finals(s["id"])
            scores = [finals.get(p["id"]) for p in b.problems]
            other = store.get("students", st)
            rows.append({"student_id": st, "student_name": (other or {}).get("name") or None, "status": "Approved (not on the class roster)",
                         "submission_id": s["id"], "scores": scores, "edited": [False] * len(b.problems), "total": round(sum(v or 0 for v in scores), 2),
                         "just_approved": False})
    for s in b.subs:  # papers not matched to anyone yet
        if not s.get("student_id"):
            rows.append({"student_id": None, "student_name": None, "status": "Student not identified", "submission_id": s["id"], "scores": [None] * len(b.problems), "edited": [False] * len(b.problems), "total": None, "just_approved": False})
    return {"activity": activity_summary(b), "columns": [f"{PROBLEM_PREFIX[b.subject]}{p['position']}" for p in b.problems], "rows": rows}


def approved_grades(store: Store, activity_id: str) -> list[dict]:
    b = Bundle(store, activity_id)
    out = []
    for s in b.subs:
        if s["status"] != "approved" or not s.get("student_id"):
            continue
        rev = b.reviews.get(s["id"]) or {}
        out.append({"student_ref": s["student_id"], "score": b.final_total(s["id"]), "max_score": float(b.activity["total_points"]), "approved_at": rev.get("approved_at")})
    return out

