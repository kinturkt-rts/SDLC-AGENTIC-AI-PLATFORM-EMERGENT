"""Shared FastAPI dependencies — auth, DB session, RBAC."""
from __future__ import annotations

from typing import Annotated

import jwt as pyjwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import decode_access_token

_bearer = HTTPBearer(auto_error=False)

# ── DB session shorthand ──
DbSession = Annotated[Session, Depends(get_db)]


# ── Auth ──
class CurrentUser:
    """Token-derived user context."""

    def __init__(self, user_id: str, username: str, role: str) -> None:
        self.user_id = user_id
        self.username = username
        self.role = role


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> CurrentUser:
    """Validate JWT bearer token and return the requesting user."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    token = credentials.credentials
    try:
        payload = decode_access_token(token)
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except pyjwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
    return CurrentUser(
        user_id=payload["sub"],
        username=payload.get("username", ""),
        role=payload.get("role", "employee"),
    )


def require_contributor_or_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> CurrentUser:
    """Require contributor or admin role."""
    user = get_current_user(credentials)
    if user.role not in ("contributor", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )
    return user


def require_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> CurrentUser:
    """Require admin role."""
    user = get_current_user(credentials)
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )
    return user


# Annotated shortcuts
AuthUser = Annotated[CurrentUser, Depends(get_current_user)]
ContributorOrAdmin = Annotated[CurrentUser, Depends(require_contributor_or_admin)]
AdminUser = Annotated[CurrentUser, Depends(require_admin)]
