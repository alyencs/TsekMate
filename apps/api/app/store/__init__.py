from __future__ import annotations

from functools import lru_cache

from ..config import get_settings
from .base import Store


@lru_cache
def get_store() -> Store:
    s = get_settings()
    if s.use_supabase:
        from .supabase_store import SupabaseStore

        return SupabaseStore(s.supabase_url, s.supabase_service_key, s.supabase_bucket)  # type: ignore[arg-type]
    from .memory import MemoryStore

    return MemoryStore(s.public_api_url, s.signing_secret)
