"""Shared FastAPI dependencies — auth, DB session."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Header, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db

# ── DB session shorthand ─────────────────────────────────────────────────────

DbSession = Annotated[Session, Depends(get_db)]


# ── API Key Auth ──────────────────────────────────────────────────────────────

def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> str:
    """Validate API key for write operations.

    Raises HTTPException(401) if key is missing or invalid. The Header must default
    to None (not be required) so FastAPI does not short-circuit with 422 before our
    401 check runs.
    """
    settings = get_settings()
    if not x_api_key or x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key"
        )
    return x_api_key


ApiKeyAuth = Annotated[str, Depends(require_api_key)]