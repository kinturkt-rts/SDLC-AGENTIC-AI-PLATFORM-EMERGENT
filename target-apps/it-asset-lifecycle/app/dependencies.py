"""FastAPI dependencies — auth, DB session, role guards."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.security import decode_access_token

# Type alias for injected DB session
DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DbSession,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> User:
    """Validate Bearer JWT and return the authenticated User ORM object."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization[len("Bearer "):]
    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*allowed_roles: str):
    """Factory that returns a dependency enforcing role membership."""
    def _guard(current_user: CurrentUser) -> User:
        if current_user.role not in allowed_roles and str(current_user.role) not in allowed_roles:
            raise HTTPException(status_code=403, detail="Forbidden")
        return current_user
    return _guard
