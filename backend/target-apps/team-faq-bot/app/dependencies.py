"""Shared FastAPI dependencies — API-key auth per design Rules."""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db

# ── DB session shorthand ─────────────────────────────────────────────────────
DbSession = Annotated[Session, Depends(get_db)]


# ── API-key auth ─────────────────────────────────────────────────────────────
def require_api_key(
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> str:
    """Validate user-level API key."""
    settings = get_settings()
    if not x_api_key or x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return x_api_key


def require_admin_api_key(
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> str:
    """Validate admin-level API key."""
    settings = get_settings()
    if not x_api_key or x_api_key != settings.admin_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin API key",
        )
    return x_api_key


ApiKeyAuth = Annotated[str, Depends(require_api_key)]
AdminApiKeyAuth = Annotated[str, Depends(require_admin_api_key)]
