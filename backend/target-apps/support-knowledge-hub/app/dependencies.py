"""Shared FastAPI dependencies — auth, DB session, RBAC."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Header, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import decode_access_token

# ── DB session shorthand ─────────────────────────────────────────────────────
DbSession = Annotated[Session, Depends(get_db)]


# ── Auth ─────────────────────────────────────────────────────────────────────
class AuthenticatedUser:
    """Minimal token-derived user context injected by the auth dependency."""

    def __init__(self, user_id: str, role: str) -> None:
        self.user_id = user_id
        self.role = role


def get_current_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> AuthenticatedUser:
    """Validate JWT bearer token and return the requesting user."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )
    token = authorization.removeprefix("Bearer ").strip()
    payload = decode_access_token(token)
    user_id = payload.get("sub")
    role = payload.get("role")
    if not user_id or not role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    return AuthenticatedUser(user_id=user_id, role=role)


AuthUser = Annotated[AuthenticatedUser, Depends(get_current_user)]


def require_role(*allowed_roles: str):
    """Factory that returns a dependency requiring the user to have one of allowed_roles."""

    def _checker(
        current_user: AuthUser,
    ) -> AuthenticatedUser:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden",
            )
        return current_user

    return _checker
