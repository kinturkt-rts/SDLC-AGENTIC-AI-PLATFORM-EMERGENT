"""Shared FastAPI dependencies — auth, DB session, RBAC."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Header, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.security import decode_access_token

# ── DB session shorthand ──
DbSession = Annotated[Session, Depends(get_db)]


# ── Auth ──

class CurrentUser:
    """Minimal token-derived user context."""

    def __init__(self, user_id: str, email: str, role: str) -> None:
        self.user_id = user_id
        self.email = email
        self.role = role


def get_current_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> CurrentUser:
    """Validate JWT bearer token and return requesting user context."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )
    token = authorization[7:]
    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    user_id = payload.get("sub")
    role = payload.get("role", "")
    email = payload.get("email", "")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    return CurrentUser(user_id=user_id, email=email, role=role)


AuthUser = Annotated[CurrentUser, Depends(get_current_user)]


# ── RBAC helpers ──

def require_admin(current_user: AuthUser) -> CurrentUser:
    if current_user.role != "facilities_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


def require_admin_or_leadership(current_user: AuthUser) -> CurrentUser:
    if current_user.role not in ("facilities_admin", "leadership"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin or leadership access required")
    return current_user


AdminUser = Annotated[CurrentUser, Depends(require_admin)]
AdminOrLeadership = Annotated[CurrentUser, Depends(require_admin_or_leadership)]
