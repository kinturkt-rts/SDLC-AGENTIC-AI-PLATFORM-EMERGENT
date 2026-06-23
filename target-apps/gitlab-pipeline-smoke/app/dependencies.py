"""Shared FastAPI dependencies — API key auth and DB session."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db

DbSession = Annotated[Session, Depends(get_db)]


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> str:
    """Validate API key for write operations (401 if missing or wrong)."""
    settings = get_settings()
    if not x_api_key or x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return x_api_key


AuthKey = Annotated[str, Depends(require_api_key)]
