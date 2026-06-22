"""FastAPI dependencies — API key auth (two-tier)."""
from __future__ import annotations

from typing import Annotated

import bcrypt
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.api_key import ApiKey


def _verify_key(plain: str, hashed: str) -> bool:
    """Check an API key against its bcrypt hash."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> ApiKey:
    """Validate the API key against the api_keys table. Returns the ApiKey row."""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing API key")

    settings = get_settings()

    # Fast-path: compare against env-based keys first (allows tests without DB rows)
    if settings.api_key_standard and x_api_key == settings.api_key_standard:
        # Return a pseudo-ApiKey for the standard tier
        fake = ApiKey(id="env-standard", key_hash="", tier="standard")
        return fake
    if settings.api_key_admin and x_api_key == settings.api_key_admin:
        fake = ApiKey(id="env-admin", key_hash="", tier="admin")
        return fake

    # DB lookup
    from sqlalchemy import select
    rows = db.scalars(select(ApiKey)).all()
    for row in rows:
        if _verify_key(x_api_key, row.key_hash):
            return row

    raise HTTPException(status_code=401, detail="Invalid API key")


def require_admin(
    api_key: ApiKey = Depends(require_api_key),
) -> ApiKey:
    """Only admin-tier keys pass."""
    if api_key.tier != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return api_key


# Annotated shortcuts
DbSession = Annotated[Session, Depends(get_db)]
AuthKey = Annotated[ApiKey, Depends(require_api_key)]
AdminKey = Annotated[ApiKey, Depends(require_admin)]
