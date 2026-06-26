"""Locations router — POST /api/v1/sites/{site_id}/locations."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.dependencies import AdminUser, DbSession
from app.models.location import Location
from app.models.site import Site
from schemas.location import LocationCreate, LocationOut

router = APIRouter()


@router.post("", response_model=LocationOut, status_code=status.HTTP_201_CREATED)
def create_location(
    site_id: str,
    body: LocationCreate,
    db: DbSession,
    current_user: AdminUser,
) -> Location:
    site = db.scalars(select(Site).where(Site.id == site_id)).first()
    if not site:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    loc = Location(
        site_id=site_id,
        floor=body.floor,
        area_label=body.area_label,
    )
    db.add(loc)
    db.commit()
    db.refresh(loc)
    return loc
