"""Shared FastAPI dependencies — API-key auth per design §5 Rules."""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db

# ── DB session shorthand ───────────────────────────────────────────────────
DbSession = Annotated[Session, Depends(get_db)]


# ── API-key auth ───────────────────────────────────────────────────────
def verify_api_key(
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> str:
    """Validate X-API-Key header against settings.API_KEY.

    Returns the verified key on success; raises 401 otherwise.
    """
    settings = get_settings()
    if not x_api_key or x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return x_api_key
