"""Sites router — CRUD for facility sites."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.dependencies import AdminUser, DbSession
from app.models.site import Site
from schemas.site import SiteCreate, SiteOut, SiteUpdate

router = APIRouter()


@router.post("", response_model=SiteOut, status_code=status.HTTP_201_CREATED)
def create_site(body: SiteCreate, db: DbSession, current_user: AdminUser) -> Site:
    site = Site(
        site_code=body.site_code,
        name=body.name,
        address_line=body.address_line,
        active=body.active,
    )
    db.add(site)
    db.commit()
    db.refresh(site)
    return site


@router.patch("/{site_id}", response_model=SiteOut)
def update_site(site_id: str, body: SiteUpdate, db: DbSession, current_user: AdminUser) -> Site:
    site = db.scalars(select(Site).where(Site.id == site_id)).first()
    if not site:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    updates = body.model_dump(exclude_unset=True)
    for k, v in updates.items():
        setattr(site, k, v)
    db.commit()
    db.refresh(site)
    return site
