"""Supabase (PostgreSQL + Storage) backend using supabase-py and the service key (server side only)."""
from __future__ import annotations

from typing import Any

from .base import TABLES, Store

# JSON-ish columns are stored as jsonb; Postgres reserves "order", so problems use "position" in both stores.


class SupabaseStore(Store):
    kind = "supabase"

    def __init__(self, url: str, key: str, bucket: str) -> None:
        from supabase import create_client

        self._client = create_client(url, key)
        self._bucket = bucket

    def _t(self, table: str):
        return self._client.table(table)

    def select(self, table: str, **eq: Any) -> list[dict]:
        q = self._t(table).select("*")
        for k, v in eq.items():
            q = q.is_(k, "null") if v is None else q.eq(k, v)
        return q.execute().data or []

    def select_in(self, table: str, column: str, values: list[Any]) -> list[dict]:
        if not values:
            return []
        out: list[dict] = []
        values = list(values)
        for i in range(0, len(values), 150):  # keep URLs short
            out += self._t(table).select("*").in_(column, values[i : i + 150]).execute().data or []
        return out

    def insert(self, table: str, rows: dict | list[dict]) -> list[dict]:
        rows = rows if isinstance(rows, list) else [rows]
        out: list[dict] = []
        for i in range(0, len(rows), 200):
            out += self._t(table).upsert(rows[i : i + 200]).execute().data or []
        return out

    def update(self, table: str, row_id: str, patch: dict) -> dict:
        data = self._t(table).update(patch).eq("id", row_id).execute().data
        if not data:
            raise KeyError(f"{table}/{row_id} not found")
        return data[0]

    def delete(self, table: str, **eq: Any) -> None:
        q = self._t(table).delete()
        for k, v in eq.items():
            q = q.eq(k, v)
        q.execute()

    def put_image(self, path: str, data: bytes, content_type: str) -> None:
        self._client.storage.from_(self._bucket).upload(path, data, {"content-type": content_type, "upsert": "true"})

    def get_image(self, path: str) -> tuple[bytes, str] | None:
        try:
            data = self._client.storage.from_(self._bucket).download(path)
        except Exception:
            return None
        ct = "image/png" if path.endswith(".png") else "image/jpeg"
        return data, ct

    def delete_image(self, path: str) -> None:
        self._client.storage.from_(self._bucket).remove([path])

    def signed_url(self, path: str, expires_in: int = 3600) -> str:
        res = self._client.storage.from_(self._bucket).create_signed_url(path, expires_in)
        return res.get("signedURL") or res.get("signedUrl") or ""

    def reset(self) -> None:
        # Children first (foreign keys).
        for table in reversed(TABLES):
            self._t(table).delete().neq("id", "__never__").execute()
        storage = self._client.storage.from_(self._bucket)
        for folder in ("seed", "uploads"):
            while True:
                items = storage.list(folder, {"limit": 1000}) or []
                names = [f"{folder}/{i['name']}" for i in items if i.get("name")]
                if not names:
                    break
                storage.remove(names)
