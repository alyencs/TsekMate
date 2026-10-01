"""In-app notifications created from real events (uploads, grading, retries)."""
from __future__ import annotations

from ..store.base import Store, new_id, now_iso


def add(store: Store, kind: str, title: str, body: str = "", link: str | None = None, activity_id: str | None = None,
        submission_id: str | None = None, created_at: str | None = None, read: bool = False) -> dict:
    row = {
        "id": f"n-{new_id()[:12]}",
        "kind": kind,
        "title": title,
        "body": body,
        "link": link,
        "activity_id": activity_id,
        "submission_id": submission_id,
        "read": read,
        "created_at": created_at or now_iso(),
    }
    store.insert("notifications", row)
    return row


def listing(store: Store, limit: int = 30) -> dict:
    rows = sorted(store.select("notifications"), key=lambda r: r["created_at"], reverse=True)
    return {"unread": sum(1 for r in rows if not r["read"]), "items": rows[:limit]}


def mark_read(store: Store, notification_id: str | None = None) -> dict:
    rows = store.select("notifications", read=False) if notification_id is None else [r for r in [store.get("notifications", notification_id)] if r]
    for r in rows:
        store.update("notifications", r["id"], {"read": True})
    return listing(store)
