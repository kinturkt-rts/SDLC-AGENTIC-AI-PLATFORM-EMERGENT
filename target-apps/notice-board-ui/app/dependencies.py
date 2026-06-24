"""Shared FastAPI dependencies — organizer auth, DB session."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db

# ── DB session shorthand ─────────────────────────────────────────────────────

DbSession = Annotated[Session, Depends(get_db)]


# ── Organizer secret auth ────────────────────────────────────────────────────

def require_organizer(
    x_organizer_secret: str | None = Header(default=None, alias="X-Organizer-Secret"),
) -> str:
    """Validates the shared organizer secret for write operations.

    Returns the secret on success; raises 401 on missing/invalid.
    """
    settings = get_settings()
    expected = (settings.organizer_secret or "").strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ORGANIZER_SECRET is not configured on the server.",
        )
    if not x_organizer_secret or x_organizer_secret != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing organizer secret",
        )
    return x_organizer_secret


OrganizerAuth = Annotated[str, Depends(require_organizer)]
