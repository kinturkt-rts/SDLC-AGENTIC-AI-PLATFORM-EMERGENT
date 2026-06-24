"""Shared FastAPI dependencies — API-key auth, DB session, RBAC."""
from __future__ import annotations

import hashlib
from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db

# ── DB session shorthand ─────────────────────────────────────

DbSession = Annotated[Session, Depends(get_db)]


# ── API-Key Auth ────────────────────────────────────────

def require_api_key(
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> str:
    """Validate API key header against configured value. Returns the role."""
    settings = get_settings()
    if not x_api_key or x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return "admin"  # single dev key → admin role for dev simplicity


# For multi-key RBAC via DB lookup (production pattern)
def get_api_key_role(
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> str:
    """Look up API key in the api_keys table. Returns role string."""
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    # Hash the key with SHA-256 for lookup
    key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
    from app.models.api_key import ApiKey
    api_key_row = db.query(ApiKey).filter(
        ApiKey.key_hash == key_hash,
        ApiKey.active == True,  # noqa: E712
    ).first()
    if not api_key_row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return api_key_row.role


ApiKeyRole = Annotated[str, Depends(require_api_key)]


def require_viewer(role: str = Depends(require_api_key)) -> str:
    """Viewer+ (any authenticated role)."""
    return role


def require_editor(role: str = Depends(require_api_key)) -> str:
    """Editor+ roles: editor, admin."""
    if role not in ("editor", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Editor role required",
        )
    return role


def require_admin(role: str = Depends(require_api_key)) -> str:
    """Admin only."""
    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return role


ViewerRole = Annotated[str, Depends(require_viewer)]
EditorRole = Annotated[str, Depends(require_editor)]
AdminRole = Annotated[str, Depends(require_admin)]
