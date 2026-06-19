"""Technicians router."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import CurrentUser
from app.models.technician import Technician
from schemas.technician import TechnicianOut

router = APIRouter(tags=["technicians"])


@router.get("", response_model=list[TechnicianOut])
def list_technicians(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    active_only: bool = Query(default=True),
) -> list[TechnicianOut]:
    """List technicians. All authenticated roles may access."""
    query = db.query(Technician)
    if active_only:
        query = query.filter(Technician.is_active == True)  # noqa: E712
    return list(query.all())  # type: ignore[return-value]
