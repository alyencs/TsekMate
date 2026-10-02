"""Teacher settings and profile (one teacher account). Stored in the app_settings table so they persist."""
from __future__ import annotations

from ..config import get_settings
from ..grading import scoring
from ..store.base import Store, now_iso

DEFAULT_PROFILE = {"name": "Prof. Ana Reyes", "department": "General Education Department", "title": "Instructor"}


def defaults() -> dict:
    return {
        "confidence_threshold": 0.75,
        "default_feedback_style": "hint_only",
        "default_accept_alternate": True,
        "default_rubric_mode": "manual",
        "delete_images_on_approve": get_settings().delete_images_on_approve,
        # "fast": graded right away at the standard price. "saver": "Grade all" goes through the Batch API at half
        # price, usually within an hour (at most 24 hours).
        "grading_mode": "fast",
    }


def get(store: Store) -> dict:
    row = store.get("app_settings", "settings")
    return {**defaults(), **(row["value"] if row else {})}


def apply(store: Store) -> dict:
    """Load settings into the running process (the confidence threshold is used by routing)."""
    s = get(store)
    scoring.THRESHOLD = float(s["confidence_threshold"])
    return s


def update(store: Store, patch: dict) -> dict:
    current = get(store)
    old_threshold = current["confidence_threshold"]
    current.update({k: v for k, v in patch.items() if v is not None})
    store.insert("app_settings", {"id": "settings", "value": current, "updated_at": now_iso()})
    apply(store)
    rerouted = 0
    if current["confidence_threshold"] != old_threshold:
        rerouted = reroute(store)
    return {**current, "rerouted": rerouted}


def reroute(store: Store) -> int:
    """Re-apply confidence routing to papers that are not approved yet (needs_review <-> ready)."""
    from .core import Bundle

    changed = 0
    for a in store.select("activities"):
        b = Bundle(store, a["id"])
        for s in b.subs:
            if s["status"] not in ("needs_review", "ready"):
                continue
            new = "needs_review" if (scoring.needs_teacher(b.effective(s["id"])) or not s.get("student_id")) else "ready"
            if new != s["status"] and store.update_where("submissions", s["id"], {"status": new, "updated_at": now_iso()}, status=s["status"]):
                changed += 1
    return changed


def profile(store: Store) -> dict:
    row = store.get("app_settings", "profile")
    return {**DEFAULT_PROFILE, **(row["value"] if row else {})}


def update_profile(store: Store, patch: dict) -> dict:
    p = {**profile(store), **{k: v.strip() for k, v in patch.items() if isinstance(v, str)}}
    store.insert("app_settings", {"id": "profile", "value": p, "updated_at": now_iso()})
    return p
