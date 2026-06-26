"""Security utilities — JWT and bcrypt."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import get_settings


def hash_password(plain: str) -> str:
    """Hash password with bcrypt cost factor 12."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(subject: str, role: str) -> str:
    """Create a JWT with user_id and role claims."""
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_ttl_hours)
    payload = {
        "sub": subject,
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT. Raises jwt.PyJWTError on failure."""
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
