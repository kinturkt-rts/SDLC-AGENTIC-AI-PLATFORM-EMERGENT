"""Shared FastAPI dependencies — API-key auth (two-tier: read + write)."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db

# ── DB session shorthand ──────────────────────────────────────────────────────
DbSession = Annotated[Session, Depends(get_db)]


# ── Auth — two-tier API-key ───────────────────────────────────────────────────
def require_write_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> str:
    """Guard state-changing endpoints (POST, PUT, PATCH)."""
    settings = get_settings()
    if not x_api_key or x_api_key != settings.write_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return x_api_key


def require_read_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> str:
    """Guard read endpoints (GET collection/detail)."""
    settings = get_settings()
    valid_keys = {settings.write_api_key, settings.read_api_key}
    if not x_api_key or x_api_key not in valid_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return x_api_key


WriteKey = Annotated[str, Depends(require_write_key)]
ReadKey = Annotated[str, Depends(require_read_key)]
