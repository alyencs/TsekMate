"""Storage interface. Both backends store plain dict rows keyed by a text `id`."""
from __future__ import annotations

import hashlib
import hmac
import time
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

TABLES = [
    "students",
    "activities",
    "problems",
    "rubrics",
    "rubric_templates",
    "submissions",
    "ai_results",
    "teacher_reviews",
    "class_summaries",
    "parent_messages",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


class Store(ABC):
    kind: str = "base"

    # --- rows ---
    @abstractmethod
    def select(self, table: str, **eq: Any) -> list[dict]: ...

    @abstractmethod
    def select_in(self, table: str, column: str, values: list[Any]) -> list[dict]: ...

    @abstractmethod
    def insert(self, table: str, rows: dict | list[dict]) -> list[dict]: ...

    @abstractmethod
    def update(self, table: str, row_id: str, patch: dict) -> dict: ...

    @abstractmethod
    def delete(self, table: str, **eq: Any) -> None: ...

    def get(self, table: str, row_id: str) -> dict | None:
        rows = self.select(table, id=row_id)
        return rows[0] if rows else None

    def one(self, table: str, **eq: Any) -> dict | None:
        rows = self.select(table, **eq)
        return rows[0] if rows else None

    # --- images (private bucket) ---
    @abstractmethod
    def put_image(self, path: str, data: bytes, content_type: str) -> None: ...

    @abstractmethod
    def get_image(self, path: str) -> tuple[bytes, str] | None: ...

    @abstractmethod
    def delete_image(self, path: str) -> None: ...

    @abstractmethod
    def signed_url(self, path: str, expires_in: int = 3600) -> str: ...

    @abstractmethod
    def reset(self) -> None:
        """Delete every row and image. Used by the seed script."""


def sign(path: str, expires: int, secret: str) -> str:
    return hmac.new(secret.encode(), f"{path}:{expires}".encode(), hashlib.sha256).hexdigest()[:32]


def local_signed_url(base: str, path: str, secret: str, expires_in: int) -> str:
    expires = int(time.time()) + expires_in
    return f"{base}/api/images/{path}?expires={expires}&sig={sign(path, expires, secret)}"


def verify_signature(path: str, expires: int, sig: str, secret: str) -> bool:
    return expires >= time.time() and hmac.compare_digest(sign(path, expires, secret), sig)
