"""Auth and shared dependencies."""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.user import User

# Shorthand
DbSession = Annotated[Session, Depends(get_db)]


def require_user_token(
    x_user_token: Optional[str] = Header(default=None, alias="X-User-Token"),
) -> str:
    """Validate X-User-Token header is present."""
    if not x_user_token:
        raise HTTPException(status_code=401, detail="Missing X-User-Token header")
    return x_user_token


def require_admin_key(
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
) -> str:
    """Validate X-Admin-Key header matches config."""
    settings = get_settings()
    if not x_admin_key or x_admin_key != settings.admin_key:
        raise HTTPException(status_code=401, detail="Invalid or missing admin key")
    return x_admin_key


def get_current_user(
    db: DbSession,
    user_token: str = Depends(require_user_token),
) -> User:
    """Resolve user from token stored in users.user_token column."""
    user = db.query(User).filter(User.user_token == user_token).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid user token")
    return user
