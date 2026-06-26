"""Desks router — public list, admin create/patch."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import DbSession, require_admin_key
from app.models.desk import Desk
from app.models.zone import Zone
from schemas.desk import DeskCreate, DeskOut, DeskUpdate

router = APIRouter()


@router.get("/", response_model=list[DeskOut])
def list_desks(
    db: DbSession,
    zone: Optional[str] = Query(default=None, description="Filter by zone name (north|south|lab)"),
    active: Optional[bool] = Query(default=None, description="Filter by active status"),
):
    """List desks with optional zone/active filters."""
    query = db.query(Desk)

    if zone:
        zone_obj = db.query(Zone).filter(Zone.name == zone).first()
        if zone_obj:
            query = query.filter(Desk.zone_id == zone_obj.id)
        else:
            return []  # No matching zone, return empty

    if active is not None:
        query = query.filter(Desk.is_active == active)

    return query.all()


@router.post("/", response_model=DeskOut, status_code=201)
def create_desk(
    body: DeskCreate,
    db: DbSession,
    _admin: str = Depends(require_admin_key),
):
    """Create a new desk (admin only)."""
    # Resolve zone by name
    zone = db.query(Zone).filter(Zone.name == body.zone).first()
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone '{body.zone}' not found")

    desk = Desk(zone_id=zone.id, label=body.label, is_active=True)
    db.add(desk)
    db.commit()
    db.refresh(desk)
    return desk


@router.patch("/{desk_id}", response_model=DeskOut)
def update_desk(
    desk_id: str,
    body: DeskUpdate,
    db: DbSession,
    _admin: str = Depends(require_admin_key),
):
    """Partial update a desk (admin only)."""
    desk = db.query(Desk).filter(Desk.id == desk_id).first()
    if not desk:
        raise HTTPException(status_code=404, detail="Desk not found")

    updates = body.model_dump(exclude_unset=True)
    for key, value in updates.items():
        if key == "zone":
            zone = db.query(Zone).filter(Zone.name == value).first()
            if not zone:
                raise HTTPException(status_code=404, detail=f"Zone '{value}' not found")
            desk.zone_id = zone.id
        else:
            setattr(desk, key, value)

    db.commit()
    db.refresh(desk)
    return desk
