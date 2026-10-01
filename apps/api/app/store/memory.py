"""In-process store: a test double used for tests and local runs before a Supabase project exists."""
from __future__ import annotations

import copy
import threading
from typing import Any

from .base import TABLES, Store, local_signed_url


class MemoryStore(Store):
    kind = "memory"

    def __init__(self, public_url: str, secret: str) -> None:
        self._rows: dict[str, dict[str, dict]] = {t: {} for t in TABLES}
        self._images: dict[str, tuple[bytes, str]] = {}
        self._lock = threading.RLock()
        self._public_url = public_url
        self._secret = secret

    def select(self, table: str, **eq: Any) -> list[dict]:
        with self._lock:
            return [copy.deepcopy(r) for r in self._rows[table].values() if all(r.get(k) == v for k, v in eq.items())]

    def select_in(self, table: str, column: str, values: list[Any]) -> list[dict]:
        vs = set(values)
        with self._lock:
            return [copy.deepcopy(r) for r in self._rows[table].values() if r.get(column) in vs]

    def insert(self, table: str, rows: dict | list[dict]) -> list[dict]:
        rows = rows if isinstance(rows, list) else [rows]
        with self._lock:
            for r in rows:
                self._rows[table][r["id"]] = copy.deepcopy(r)
        return copy.deepcopy(rows)

    def update(self, table: str, row_id: str, patch: dict) -> dict:
        with self._lock:
            row = self._rows[table].get(row_id)
            if row is None:
                raise KeyError(f"{table}/{row_id} not found")
            row.update(copy.deepcopy(patch))
            return copy.deepcopy(row)

    def delete(self, table: str, **eq: Any) -> None:
        with self._lock:
            for rid in [rid for rid, r in self._rows[table].items() if all(r.get(k) == v for k, v in eq.items())]:
                del self._rows[table][rid]

    def put_image(self, path: str, data: bytes, content_type: str) -> None:
        with self._lock:
            self._images[path] = (data, content_type)

    def get_image(self, path: str) -> tuple[bytes, str] | None:
        return self._images.get(path)

    def delete_image(self, path: str) -> None:
        with self._lock:
            self._images.pop(path, None)

    def signed_url(self, path: str, expires_in: int = 3600) -> str:
        return local_signed_url(self._public_url, path, self._secret, expires_in)

    def reset(self) -> None:
        with self._lock:
            self._rows = {t: {} for t in TABLES}
            self._images.clear()
