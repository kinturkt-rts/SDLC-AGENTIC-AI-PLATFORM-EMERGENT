"""Shared FastAPI dependencies — API-key auth, DB session, RBAC."""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db

DbSession = Annotated[Session, Depends(get_db)]


class CurrentUser:
    """User context resolved from API key."""

    def __init__(self, user_id: str, username: str, role: str, technician_id: str | None) -> None:
        self.user_id = user_id
        self.username = username
        self.role = role
        self.technician_id = technician_id


def get_current_user(
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> CurrentUser:
    """Resolve API key to a user record."""
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
        )
    from app.models.user import User
    try:
        user = db.query(User).filter(User.api_key == x_api_key).first()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    return CurrentUser(
        user_id=str(user.id),
        username=user.username,
        role=user.role,
        technician_id=str(user.technician_id) if user.technician_id else None,
    )


AuthUser = Annotated[CurrentUser, Depends(get_current_user)]


def _require_dispatcher(current_user: AuthUser) -> CurrentUser:
    if current_user.role != "dispatcher":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return current_user


def _require_dispatcher_or_owner(current_user: AuthUser) -> CurrentUser:
    if current_user.role not in ("dispatcher", "owner"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return current_user


DispatcherUser = Annotated[CurrentUser, Depends(_require_dispatcher)]
DispatcherOrOwner = Annotated[CurrentUser, Depends(_require_dispatcher_or_owner)]
