"""Authentication and password helpers.

- bcrypt hashing via the `bcrypt` package (NFR-1).
- JWT HS256 token issue/decode via python-jose (NFR-2).
- Slug derivation utility (FR-4).
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.config import settings


def hash_password(plain: str) -> str:
    """Return a bcrypt hash of `plain`. Used by tests / future user-mgmt code."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Return True when `plain` matches the bcrypt-hashed value, else False.

    Wrapped in try/except so malformed seed hashes never crash the login route;
    they simply fail verification and surface as 401 (FR-2).
    """
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(
    *,
    subject: str,
    role: str,
    expires_minutes: int | None = None,
) -> tuple[str, int]:
    """Return `(jwt_token, expires_in_seconds)`.

    `subject` is placed in the standard `sub` claim; `role` is a custom claim
    consumed by `app.deps.require_role`. Token uses HS256 signed with
    `JWT_SECRET_KEY`; expiry defaults to `JWT_EXPIRE_MINUTES`.
    """
    minutes = expires_minutes if expires_minutes is not None else settings.jwt_expire_minutes
    expires_in_seconds = minutes * 60
    now = datetime.now(tz=timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=minutes)).timestamp()),
    }
    token = jwt.encode(
        payload,
        settings.jwt_secret_key or "test-secret-do-not-use-in-prod",
        algorithm=settings.jwt_algorithm,
    )
    return token, expires_in_seconds


def decode_access_token(token: str) -> dict[str, Any]:
    """Return the decoded claims dict.

    Raises `JWTError` (re-exported below) on invalid signature, malformed token,
    or expired `exp`. Routers translate this into HTTP 401 (FR-3).
    """
    return jwt.decode(
        token,
        settings.jwt_secret_key or "test-secret-do-not-use-in-prod",
        algorithms=[settings.jwt_algorithm],
    )


# Re-export so routers don't need to import python-jose directly.
TokenDecodeError = JWTError


_slug_strip_re = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    """Lower-case URL-safe slug: strip diacritics-free non-alphanumerics → hyphens.

    Implementation detail per PRD assumption — keeps deterministic output and
    bounded length so the DB unique index can act as the integrity backstop.
    """
    lowered = value.strip().lower()
    slug = _slug_strip_re.sub("-", lowered).strip("-")
    return slug[:100] or "untitled"
