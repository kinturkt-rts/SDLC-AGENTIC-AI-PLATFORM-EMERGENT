"""Shared FastAPI dependencies — auth, DB session, RBAC."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import decode_token

_bearer = HTTPBearer(auto_error=True)

# ── DB session shorthand ─────────────────────────────────────────────────────

DbSession = Annotated[Session, Depends(get_db)]


# ── Auth ─────────────────────────────────────────────────────────────────────

class CurrentUser:
    """Token-derived user context injected by the auth dependency."""

    def __init__(self, user_id: str, email: str, role: str) -> None:
        self.user_id = user_id
        self.email = email
        self.role = role


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
    db: DbSession,
) -> CurrentUser:
    """Validate JWT bearer token and return the requesting user."""
    from app.models.user import User
    
    token = credentials.credentials
    payload = decode_token(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id: str = payload.get("sub")
    role: str = payload.get("role")
    
    if user_id is None or role is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing required claims",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verify user exists in database
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verify role matches database (security check)
    if user.role != role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token role mismatch",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return CurrentUser(user_id=user.id, email=user.email, role=user.role)


AuthUser = Annotated[CurrentUser, Depends(get_current_user)]


# ── Role-based access control ────────────────────────────────────────────────

def require_auditor(current_user: AuthUser) -> CurrentUser:
    """Require auditor role."""
    if current_user.role not in ["auditor"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Auditor access required"
        )
    return current_user


def require_executive(current_user: AuthUser) -> CurrentUser:
    """Require executive role."""
    if current_user.role not in ["executive"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Executive access required"
        )
    return current_user


def require_auditor_or_executive(current_user: AuthUser) -> CurrentUser:
    """Require auditor or executive role."""
    if current_user.role not in ["auditor", "executive"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Auditor or executive access required"
        )
    return current_user