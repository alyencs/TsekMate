"""Environment configuration. All values come from env vars (see .env.example)."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

API_DIR = Path(__file__).resolve().parents[1]
# Repo root when running from the monorepo; in a container (only apps/api copied) fall back to the API dir.
ROOT = API_DIR.parents[1] if len(API_DIR.parents) > 1 and (API_DIR.parents[1] / "apps").exists() else API_DIR
load_dotenv(ROOT / ".env")
load_dotenv(API_DIR / ".env")


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    def __init__(self) -> None:
        # Google Gemini (server side only; never exposed to the web app).
        self.gemini_api_key: str | None = os.getenv("GEMINI_API_KEY") or None
        self.gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.supabase_url: str | None = os.getenv("SUPABASE_URL") or None
        self.supabase_service_key: str | None = os.getenv("SUPABASE_SERVICE_KEY") or None
        self.supabase_bucket: str = os.getenv("SUPABASE_BUCKET", "submissions")
        self.delete_images_on_approve: bool = _bool("DELETE_IMAGES_ON_APPROVE")
        self.demo_mode: bool = _bool("DEMO_MODE")
        self.public_api_url: str = os.getenv("PUBLIC_API_URL", "http://localhost:8000").rstrip("/")
        self.cors_origins: list[str] = [
            o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()
        ]
        self.signing_secret: str = os.getenv("IMAGE_SIGNING_SECRET", "local-dev-only-secret")
        self.teacher_email: str = os.getenv("DEMO_TEACHER_EMAIL", "reyes@school.edu.ph")
        self.teacher_password: str = os.getenv("DEMO_TEACHER_PASSWORD", "tsekmate")
        self.demo_cache_dir: Path = ROOT / "samples" / "cache"

    @property
    def use_supabase(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
