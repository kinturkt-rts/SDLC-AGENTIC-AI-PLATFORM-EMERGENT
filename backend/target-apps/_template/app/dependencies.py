"""Shared FastAPI dependencies — auth, DB session, role guards.

Standard auth module. Do not edit per app. Import get_current_user,
CurrentUser, require_role, and DbSession; wire them onto routes.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import decode_access_token

# ── DB session shorthand ─────────────────────────────────────────────────────
DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict:
    """Extract and validate JWT from Authorization: Bearer <token>."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    token = authorization[7:]
    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    return {"user_id": payload["sub"], "role": payload["role"]}


CurrentUser = Annotated[dict, Depends(get_current_user)]


def require_role(*allowed_roles: str):
    """Factory: returns a dependency that checks the user's role."""
    def _checker(current_user: CurrentUser) -> dict:
        if current_user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden"
            )
        return current_user
    return _checker