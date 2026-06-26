"""Security utilities — JWT creation/verification and password hashing."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.config import get_settings


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(subject: str, role: str, technician_id: str | None = None) -> tuple[str, datetime]:
    """Create JWT with sub, role, and optional technician_id claims.

    Returns (token_string, expiry_datetime).
    """
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload: dict = {"sub": subject, "role": role, "exp": expire}
    if technician_id:
        payload["technician_id"] = technician_id
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, expire


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT token. Raises JWTError on failure."""
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
