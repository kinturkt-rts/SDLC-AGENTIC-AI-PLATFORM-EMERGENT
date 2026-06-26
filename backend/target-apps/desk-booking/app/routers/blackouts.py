"""Blackouts router — admin only."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import DbSession, require_admin_key
from app.models.blackout import Blackout
from app.models.desk import Desk
from schemas.blackout import BlackoutCreate, BlackoutOut

router = APIRouter()


@router.post("/", response_model=BlackoutOut, status_code=201)
def create_blackout(
    body: BlackoutCreate,
    db: DbSession,
    _admin: str = Depends(require_admin_key),
):
    """Create a blackout period (admin only)."""
    desk = db.query(Desk).filter(Desk.id == body.desk_id).first()
    if not desk:
        raise HTTPException(status_code=404, detail="Desk not found")

    if body.starts_on > body.ends_on:
        raise HTTPException(
            status_code=422,
            detail="Start date must be before or equal to end date",
        )

    blackout = Blackout(
        desk_id=body.desk_id,
        starts_on=body.starts_on,
        ends_on=body.ends_on,
        reason=body.reason,
    )
    db.add(blackout)
    db.commit()
    db.refresh(blackout)
    return blackout


@router.get("/", response_model=list[BlackoutOut])
def list_blackouts(
    db: DbSession,
    _admin: str = Depends(require_admin_key),
    desk_id: Optional[str] = Query(default=None, description="Filter by desk ID"),
):
    """List blackout periods (admin only). Optional ?desk_id filter."""
    query = db.query(Blackout)
    if desk_id:
        query = query.filter(Blackout.desk_id == desk_id)
    return query.order_by(Blackout.starts_on.desc()).all()


@router.delete("/{blackout_id}", status_code=204, response_model=None)
def delete_blackout(
    blackout_id: str,
    db: DbSession,
    _admin: str = Depends(require_admin_key),
):
    """Remove a blackout period (admin only)."""
    blackout = db.query(Blackout).filter(Blackout.id == blackout_id).first()
    if not blackout:
        raise HTTPException(status_code=404, detail="Blackout not found")

    db.delete(blackout)
    db.commit()
    return None
