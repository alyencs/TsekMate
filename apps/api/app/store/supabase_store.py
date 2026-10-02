"""Supabase (PostgreSQL + Storage) backend using supabase-py and the service key (server side only)."""
from __future__ import annotations

from typing import Any

from .base import TABLES, Store, UniqueViolation

# JSON-ish columns are stored as jsonb; Postgres reserves "order", so problems use "position" in both stores.

# Paper files are stored under their real type's extension (core.add_uploads); read them back with the same type.
CONTENT_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".pdf": "application/pdf"}


def content_type_for(path: str) -> str:
    for ext, ct in CONTENT_TYPES.items():
        if path.lower().endswith(ext):
            return ct
    return "application/octet-stream"


def _unique_guard(fn):
    """Turn a Postgres unique violation (SQLSTATE 23505) into the store's UniqueViolation."""

    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            if str(getattr(e, "code", "")) == "23505":
                raise UniqueViolation(str(getattr(e, "message", "")) or "unique violation") from None
            raise

    return wrapper


class SupabaseStore(Store):
    kind = "supabase"

    def __init__(self, url: str, key: str, bucket: str, client: Any = None) -> None:
        if client is None:
            from supabase import create_client

            client = create_client(url, key)
        self._client = client
        self._bucket = bucket

    def _t(self, table: str):
        return self._client.table(table)

    @staticmethod
    def _filter(q, eq: dict[str, Any]):
        for k, v in eq.items():
            q = q.is_(k, "null") if v is None else q.eq(k, v)
        return q

    def select(self, table: str, **eq: Any) -> list[dict]:
        return self._filter(self._t(table).select("*"), eq).execute().data or []

    def select_in(self, table: str, column: str, values: list[Any]) -> list[dict]:
        if not values:
            return []
        out: list[dict] = []
        values = list(values)
        for i in range(0, len(values), 150):  # keep URLs short
            out += self._t(table).select("*").in_(column, values[i : i + 150]).execute().data or []
        return out

    @_unique_guard
    def insert(self, table: str, rows: dict | list[dict]) -> list[dict]:
        rows = rows if isinstance(rows, list) else [rows]
        out: list[dict] = []
        for i in range(0, len(rows), 200):
            out += self._t(table).upsert(rows[i : i + 200]).execute().data or []
        return out

    @_unique_guard
    def update(self, table: str, row_id: str, patch: dict) -> dict:
        data = self._t(table).update(patch).eq("id", row_id).execute().data
        if not data:
            raise KeyError(f"{table}/{row_id} not found")
        return data[0]

    @_unique_guard
    def update_where(self, table: str, row_id: str, patch: dict, **expect: Any) -> dict | None:
        # One UPDATE ... WHERE id = ? AND <expected values>: atomic in Postgres, so a stale writer changes nothing.
        data = self._filter(self._t(table).update(patch).eq("id", row_id), expect).execute().data
        return data[0] if data else None

    def delete(self, table: str, **eq: Any) -> None:
        self._filter(self._t(table).delete(), eq).execute()

    def put_image(self, path: str, data: bytes, content_type: str) -> None:
        self._client.storage.from_(self._bucket).upload(path, data, {"content-type": content_type, "upsert": "true"})

    def get_image(self, path: str) -> tuple[bytes, str] | None:
        try:
            data = self._client.storage.from_(self._bucket).download(path)
        except Exception:
            return None
        return data, content_type_for(path)

    def delete_image(self, path: str) -> None:
        self._client.storage.from_(self._bucket).remove([path])

    def signed_url(self, path: str, expires_in: int = 3600) -> str:
        res = self._client.storage.from_(self._bucket).create_signed_url(path, expires_in)
        return res.get("signedURL") or res.get("signedUrl") or ""

    def _files_under(self, folder: str) -> list[str]:
        """Every file path under `folder`, walking sub-folders (Storage lists folders as entries without an id)."""
        storage = self._client.storage.from_(self._bucket)
        out: list[str] = []
        offset = 0
        while True:
            items = storage.list(folder, {"limit": 1000, "offset": offset}) or []
            for i in items:
                name = i.get("name")
                if not name:
                    continue
                path = f"{folder}/{name}"
                if i.get("id") is None:  # a folder
                    out += self._files_under(path)
                else:
                    out.append(path)
            if len(items) < 1000:
                return out
            offset += len(items)

    def reset(self) -> None:
        # Children first (foreign keys).
        for table in reversed(TABLES):
            self._t(table).delete().neq("id", "__never__").execute()
        storage = self._client.storage.from_(self._bucket)
        for folder in ("seed", "uploads"):
            files = self._files_under(folder)
            for i in range(0, len(files), 500):
                storage.remove(files[i : i + 500])
