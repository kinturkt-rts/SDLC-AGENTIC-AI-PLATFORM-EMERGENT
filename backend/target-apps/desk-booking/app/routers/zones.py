"""Zones router — public read."""
from __future__ import annotations

from fastapi import APIRouter

from app.dependencies import DbSession
from app.models.zone import Zone
from schemas.zone import ZoneOut

router = APIRouter()


@router.get("/", response_model=list[ZoneOut])
def list_zones(db: DbSession):
    """Return all zones."""
    zones = db.query(Zone).all()
    return zones
