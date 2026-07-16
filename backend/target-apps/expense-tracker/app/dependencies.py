"""Shared FastAPI dependencies — auth via Bearer token (employees) and X-Api-Key (managers/admins)."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db

# -- DB session shorthand --
DbSession = Annotated[Session, Depends(get_db)]


@dataclass
class Actor:
    """Resolved identity of the requesting actor."""
    id: int
    role: str  # 'employee', 'manager', 'admin'
    team_ids: list[int]  # for employees: [team_id]; for manager: scoped team_ids; admin: all


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _parse_team_ids(raw) -> list[int]:
    """Parse team_ids from either a Postgres ARRAY (list[int]) or SQLite string repr."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return [int(x) for x in raw]
    if isinstance(raw, str):
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        return [int(p) for p in parts if p.isdigit()]
    return []


def get_current_actor(
    db: DbSession,
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    x_api_key: Optional[str] = Header(default=None, alias="X-Api-Key"),
) -> Actor:
    """Resolve the requesting actor from Bearer token or X-Api-Key header."""
    from app.models.employee import Employee
    from app.models.api_key import ApiKey

    if authorization:
        parts = authorization.split(" ", 1)
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Authorization header format")
        token = parts[1]
        token_hash = _sha256(token)
        try:
            emp = db.scalars(select(Employee).where(Employee.token_hash == token_hash)).first()
        except Exception:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
        if not emp:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
        return Actor(id=emp.id, role=emp.role, team_ids=[emp.team_id] if emp.team_id else [])

    if x_api_key:
        key_hash = _sha256(x_api_key)
        try:
            api_key = db.scalars(select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.revoked_at.is_(None))).first()
        except Exception:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or revoked API key")
        if not api_key:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or revoked API key")
        team_ids = _parse_team_ids(api_key.team_ids)
        return Actor(id=api_key.id, role=api_key.role, team_ids=team_ids)

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authentication credentials")


AuthActor = Annotated[Actor, Depends(get_current_actor)]


def require_role(*roles: str):
    """Factory that returns a dependency enforcing role membership."""
    def _check(actor: AuthActor) -> Actor:
        if actor.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return actor
    return _check


AdminActor = Annotated[Actor, Depends(require_role("admin"))]
ManagerActor = Annotated[Actor, Depends(require_role("manager"))]
