"""Shared FastAPI dependencies — auth via X-API-Key header with bcrypt hash lookup."""
from __future__ import annotations

import logging
from typing import Annotated

import bcrypt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db

logger = logging.getLogger(__name__)

# ── DB session shorthand ──
DbSession = Annotated[Session, Depends(get_db)]


# ── Auth context ──
class CurrentUser:
    """Token-derived user/api-key context."""

    def __init__(self, user_id: str, email: str | None, role: str, team_id: str | None) -> None:
        self.user_id = user_id
        self.email = email
        self.role = role
        self.team_id = team_id


def _verify_hash(plain: str, hashed: str) -> bool:
    """Check plaintext against bcrypt hash."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def get_current_user(
    db: DbSession,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> CurrentUser:
    """Authenticate via X-API-Key header.

    Checks api_keys table first (admin/manager), then users.token_hash (employee).
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
        )

    from app.models.api_key import ApiKey
    from app.models.user import User

    try:
        # Try api_keys table (admin/manager)
        api_keys = db.scalars(select(ApiKey).where(ApiKey.revoked_at.is_(None))).all()
        for key_row in api_keys:
            if _verify_hash(x_api_key, key_row.key_hash):
                return CurrentUser(
                    user_id=key_row.id,
                    email=None,
                    role=key_row.role,
                    team_id=None,
                )

        # Try users table (employee tokens)
        users = db.scalars(select(User).where(User.deleted_at.is_(None))).all()
        for user_row in users:
            if user_row.token_hash and _verify_hash(x_api_key, user_row.token_hash):
                return CurrentUser(
                    user_id=user_row.id,
                    email=user_row.email,
                    role=user_row.role,
                    team_id=user_row.team_id,
                )
    except Exception as exc:
        logger.warning("Auth lookup failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key",
    )


AuthUser = Annotated[CurrentUser, Depends(get_current_user)]


def require_role(*roles: str):
    """Factory: returns a dependency that checks the user has one of the given roles."""

    def _checker(current_user: AuthUser) -> CurrentUser:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden",
            )
        return current_user

    return _checker


AdminUser = Annotated[CurrentUser, Depends(require_role("admin"))]
ManagerUser = Annotated[CurrentUser, Depends(require_role("manager", "admin"))]
EmployeeUser = Annotated[CurrentUser, Depends(require_role("employee"))]
