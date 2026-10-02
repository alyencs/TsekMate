"""Environment configuration. All values come from env vars (see .env.example).

Security-sensitive values (session secret, image signing secret, teacher password) have no known fallback:
- APP_ENV=production refuses to start when any of them is missing, short, or a known placeholder.
- In development a missing secret is replaced by a random one for this process only (sessions and image links end
  when the API restarts), and the teacher password defaults to the documented local demo password.
"""
from __future__ import annotations

import logging
import os
import secrets
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

API_DIR = Path(__file__).resolve().parents[1]
# Repo root when running from the monorepo; in a container (only apps/api copied) fall back to the API dir.
ROOT = API_DIR.parents[1] if len(API_DIR.parents) > 1 and (API_DIR.parents[1] / "apps").exists() else API_DIR
load_dotenv(ROOT / ".env")
load_dotenv(API_DIR / ".env")

log = logging.getLogger("tsekmate.config")

DEV_TEACHER_PASSWORD = "tsekmate"  # local development only; never accepted when APP_ENV=production
# Placeholders that must never be used as real secrets (earlier defaults and .env.example values included).
KNOWN_PLACEHOLDERS = {"", "change-me", "changeme", "local-dev-only-secret", "secret", "tsekmate", "password"}
MIN_SECRET_LENGTH = 32
MIN_PASSWORD_LENGTH = 10


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


class ConfigError(RuntimeError):
    """The server must not start with this configuration."""


class Settings:
    def __init__(self) -> None:
        self.app_env: str = os.getenv("APP_ENV", "development").strip().lower() or "development"
        # Anthropic Claude (server side only; never exposed to the web app).
        self.anthropic_api_key: str | None = os.getenv("ANTHROPIC_API_KEY") or None
        self.anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5")
        self.supabase_url: str | None = os.getenv("SUPABASE_URL") or None
        self.supabase_service_key: str | None = os.getenv("SUPABASE_SERVICE_KEY") or None
        self.supabase_bucket: str = os.getenv("SUPABASE_BUCKET", "submissions")
        self.delete_images_on_approve: bool = _bool("DELETE_IMAGES_ON_APPROVE")
        self.demo_mode: bool = _bool("DEMO_MODE")
        self.public_api_url: str = os.getenv("PUBLIC_API_URL", "http://localhost:8000").rstrip("/")
        self.cors_origins: list[str] = [
            o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()
        ]
        # Optional, for preview deployments, e.g. ^https://tsekmate(-[a-z0-9-]+)?\.vercel\.app$ . Unset = exact origins only.
        self.cors_origin_regex: str | None = os.getenv("CORS_ORIGIN_REGEX") or None
        self.signing_secret: str = os.getenv("IMAGE_SIGNING_SECRET", "").strip()
        self.auth_secret: str = os.getenv("AUTH_SECRET", "").strip()
        self.session_hours: float = float(os.getenv("SESSION_HOURS", "12"))
        self.teacher_email: str = os.getenv("DEMO_TEACHER_EMAIL", "areyes@university.edu.ph").strip()
        self.teacher_password: str = os.getenv("DEMO_TEACHER_PASSWORD", "")
        self.demo_cache_dir: Path = ROOT / "samples" / "cache"

        problems = self.security_problems()
        if self.is_production and problems:
            raise ConfigError("Refusing to start with APP_ENV=production: " + " ".join(problems))
        if not self.is_production:
            if self.signing_secret.lower() in KNOWN_PLACEHOLDERS:
                self.signing_secret = secrets.token_urlsafe(48)
                log.warning("IMAGE_SIGNING_SECRET is not set: using a random secret for this process (development only).")
            if self.auth_secret.lower() in KNOWN_PLACEHOLDERS:
                self.auth_secret = secrets.token_urlsafe(48)
                log.warning("AUTH_SECRET is not set: using a random secret for this process; sign-ins end on restart (development only).")
            if not self.teacher_password:
                self.teacher_password = DEV_TEACHER_PASSWORD
                log.warning("DEMO_TEACHER_PASSWORD is not set: using the local demo password (development only).")

    @property
    def is_production(self) -> bool:
        return self.app_env in {"production", "prod"}

    @property
    def use_supabase(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_key)

    def security_problems(self) -> list[str]:
        """What makes this configuration unsafe for production (empty = fine). Never includes secret values."""
        out: list[str] = []
        for name, value in (("AUTH_SECRET", self.auth_secret), ("IMAGE_SIGNING_SECRET", self.signing_secret)):
            if value.lower() in KNOWN_PLACEHOLDERS:
                out.append(f"{name} is not set (or is a placeholder).")
            elif len(value) < MIN_SECRET_LENGTH:
                out.append(f"{name} must be at least {MIN_SECRET_LENGTH} characters.")
        if self.auth_secret and self.auth_secret == self.signing_secret:
            out.append("AUTH_SECRET and IMAGE_SIGNING_SECRET must be different.")
        pw = self.teacher_password
        if not pw or pw.lower() in KNOWN_PLACEHOLDERS:
            out.append("DEMO_TEACHER_PASSWORD is not set (or is the demo/placeholder password).")
        elif len(pw) < MIN_PASSWORD_LENGTH:
            out.append(f"DEMO_TEACHER_PASSWORD must be at least {MIN_PASSWORD_LENGTH} characters.")
        if not self.teacher_email or "@" not in self.teacher_email:
            out.append("DEMO_TEACHER_EMAIL must be an email address.")
        return out


@lru_cache
def get_settings() -> Settings:
    return Settings()
