"""Server-side authentication for the teacher account.

Sign-in returns a signed bearer token (HMAC-SHA256 with AUTH_SECRET). Every protected route checks it through the
`require_teacher` dependency; the browser's stored session is only a copy of the token, never proof by itself.

A token is valid only while all of these hold:
- the signature matches (AUTH_SECRET) and it has not expired (SESSION_HOURS);
- it names the configured teacher email;
- it was issued for the current password (changing DEMO_TEACHER_PASSWORD ends every session);
- it has not been signed out (revoked token ids are stored in app_settings until they expire).

TsekMate has one teacher account, and every activity, roster, and paper belongs to it, so an authenticated teacher
is authorized for every resource. There is no second account whose data could be reached by changing an ID.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import threading
import time
import uuid
from dataclasses import dataclass

from fastapi import HTTPException, Request

from .config import get_settings
from .store import get_store
from .store.base import now_iso

REVOKED_ROW = "revoked_sessions"
MAX_FAILURES = 5
FAILURE_WINDOW = 600  # seconds
_failures: dict[str, list[float]] = {}
_fail_lock = threading.Lock()
_revoke_lock = threading.Lock()


@dataclass(frozen=True)
class Teacher:
    email: str
    token_id: str
    expires: int


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sig(payload: str, secret: str) -> str:
    return _b64(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest())


def _password_tag() -> str:
    s = get_settings()
    return hmac.new(s.auth_secret.encode(), b"pw:" + s.teacher_password.encode(), hashlib.sha256).hexdigest()[:16]


def check_password(email: str, password: str) -> bool:
    s = get_settings()
    ok_email = hmac.compare_digest(email.strip().lower().encode(), s.teacher_email.lower().encode())
    ok_pw = hmac.compare_digest(password.encode(), s.teacher_password.encode())
    return ok_email and ok_pw


def issue_token(now: float | None = None) -> tuple[str, int]:
    s = get_settings()
    now = int(now if now is not None else time.time())
    exp = now + int(s.session_hours * 3600)
    payload = _b64(json.dumps({"sub": s.teacher_email.lower(), "iat": now, "exp": exp, "jti": uuid.uuid4().hex, "pw": _password_tag()},
                              separators=(",", ":")).encode())
    return f"{payload}.{_sig(payload, s.auth_secret)}", exp


def read_token(token: str) -> Teacher | None:
    """The teacher for a valid token, else None. Never raises on malformed input."""
    s = get_settings()
    try:
        payload, sig = token.split(".")
        if not hmac.compare_digest(sig, _sig(payload, s.auth_secret)):
            return None
        data = json.loads(_unb64(payload))
        if not isinstance(data, dict) or int(data["exp"]) <= time.time():
            return None
        if data.get("sub") != s.teacher_email.lower() or data.get("pw") != _password_tag():
            return None
        jti = str(data["jti"])
    except Exception:
        return None
    if jti in _revoked():
        return None
    return Teacher(email=s.teacher_email, token_id=jti, expires=int(data["exp"]))


def _revoked() -> dict[str, int]:
    row = get_store().get("app_settings", REVOKED_ROW)
    return dict((row or {}).get("value") or {})


def revoke(teacher: Teacher) -> None:
    with _revoke_lock:  # read-modify-write: two sign-outs at once must not drop one of them
        now = time.time()
        keep = {k: v for k, v in _revoked().items() if int(v) > now}  # expired tokens are invalid anyway
        keep[teacher.token_id] = teacher.expires
        get_store().insert("app_settings", {"id": REVOKED_ROW, "value": keep, "updated_at": now_iso()})


def bearer(request: Request) -> str | None:
    h = request.headers.get("authorization") or ""
    scheme, _, value = h.partition(" ")
    return value.strip() if scheme.lower() == "bearer" and value.strip() else None


def require_teacher(request: Request) -> Teacher:
    """FastAPI dependency for every protected route."""
    token = bearer(request)
    teacher = read_token(token) if token else None
    if not teacher:
        raise HTTPException(401, "Please sign in to continue.", headers={"WWW-Authenticate": "Bearer"})
    return teacher


# ------------------------------------------------------------------ sign-in throttling (per client address)
def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def throttled(request: Request) -> bool:
    now = time.time()
    with _fail_lock:
        recent = [t for t in _failures.get(_client_key(request), []) if now - t < FAILURE_WINDOW]
        _failures[_client_key(request)] = recent
        return len(recent) >= MAX_FAILURES


def record_failure(request: Request) -> None:
    with _fail_lock:
        _failures.setdefault(_client_key(request), []).append(time.time())


def clear_failures(request: Request) -> None:
    with _fail_lock:
        _failures.pop(_client_key(request), None)
