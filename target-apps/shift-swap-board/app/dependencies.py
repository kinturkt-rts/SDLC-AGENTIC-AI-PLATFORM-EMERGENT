"""Shared FastAPI dependencies — auth, DB session, RBAC."""
from __future__ import annotations

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Header, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.security import decode_access_token

# ── DB session shorthand ─────────────────────────────────────────────────────

DbSession = Annotated[Session, Depends(get_db)]


# ── Auth ─────────────────────────────────────────────────────────────────────

class CurrentUser:
    """Token-derived user context."""

    def __init__(self, user_id: str, role: str) -> None:
        self.user_id = user_id
        self.role = role


def get_current_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> CurrentUser:
    """Validate Bearer JWT and return CurrentUser."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )
    token = authorization[7:]
    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
    user_id = payload.get("sub")
    role = payload.get("role")
    if not user_id or not role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token claims",
        )
    return CurrentUser(user_id=user_id, role=role)


AuthUser = Annotated[CurrentUser, Depends(get_current_user)]


def require_staff(current_user: AuthUser) -> CurrentUser:
    if current_user.role not in ("staff", "floor_lead", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return current_user


def require_floor_lead(current_user: AuthUser) -> CurrentUser:
    if current_user.role not in ("floor_lead", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return current_user


def require_admin(current_user: AuthUser) -> CurrentUser:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return current_user
