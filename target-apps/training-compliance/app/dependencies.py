"""FastAPI dependencies — auth, DB session, RBAC."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.entities import User
from app.security import decode_access_token


DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DbSession,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> User:
    """Extract and validate JWT from Authorization header. Returns User ORM object."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization[len("Bearer "):]
    claims = decode_access_token(token)
    if not claims or "sub" not in claims:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = db.query(User).filter(User.id == claims["sub"]).first()
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*allowed_roles: str):
    """Factory for role-based access control dependency."""
    def _check(current_user: CurrentUser) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail="Forbidden")
        return current_user
    return _check
