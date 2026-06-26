"""Shared FastAPI dependencies — JWT auth and DB session."""
from __future__ import annotations

from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import decode_access_token

# DB session shorthand
DbSession = Annotated[Session, Depends(get_db)]


class CurrentUser:
    """Token-derived user context."""

    def __init__(self, user_id: str, role: str) -> None:
        self.user_id = user_id
        self.role = role


def get_current_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> CurrentUser:
    """Validate JWT Bearer token and return user context."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
        )
    token = authorization[7:]
    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user_id = payload.get("sub")
    role = payload.get("role")
    if not user_id or not role:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token claims")
    return CurrentUser(user_id=user_id, role=role)


AuthUser = Annotated[CurrentUser, Depends(get_current_user)]


def require_manager(current_user: AuthUser) -> CurrentUser:
    """Only managers allowed."""
    if current_user.role != "manager":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Manager role required")
    return current_user


def require_manager_or_leadership(current_user: AuthUser) -> CurrentUser:
    """Managers and leadership allowed."""
    if current_user.role not in ("manager", "leadership"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Manager or leadership role required")
    return current_user


ManagerUser = Annotated[CurrentUser, Depends(require_manager)]
DashboardUser = Annotated[CurrentUser, Depends(require_manager_or_leadership)]
