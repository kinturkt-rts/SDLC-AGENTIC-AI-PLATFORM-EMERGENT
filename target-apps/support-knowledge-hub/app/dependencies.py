"""FastAPI dependencies — auth, DB session."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.security import decode_access_token


DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DbSession,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> User:
    """Extract and validate JWT from Authorization header."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization[7:]
    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_contributor(current_user: CurrentUser) -> User:
    """Require contributor, knowledge_admin, or leadership role."""
    allowed = ("contributor", "knowledge_admin", "leadership")
    if current_user.role not in allowed:
        raise HTTPException(status_code=403, detail="Forbidden")
    return current_user


def require_knowledge_admin(current_user: CurrentUser) -> User:
    """Require knowledge_admin role."""
    if current_user.role != "knowledge_admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    return current_user


def require_admin_or_leadership(current_user: CurrentUser) -> User:
    """Require knowledge_admin or leadership role."""
    if current_user.role not in ("knowledge_admin", "leadership"):
        raise HTTPException(status_code=403, detail="Forbidden")
    return current_user
