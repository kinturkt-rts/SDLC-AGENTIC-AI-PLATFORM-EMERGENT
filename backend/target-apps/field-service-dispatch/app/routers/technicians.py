"""Technicians router."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.dependencies import DbSession, DispatcherUser, DispatcherOrOwner
from app.models.technician import Technician
from schemas.technician import TechnicianCreate, TechnicianOut, TechnicianUpdate

router = APIRouter()


@router.get("/api/v1/technicians", response_model=list[TechnicianOut])
def list_technicians(
    current_user: DispatcherOrOwner,
    db: DbSession,
) -> list[TechnicianOut]:
    """List all technicians."""
    rows = db.scalars(select(Technician).order_by(Technician.name)).all()
    return [TechnicianOut.model_validate(r) for r in rows]


@router.post("/api/v1/technicians", response_model=TechnicianOut, status_code=201)
def create_technician(
    body: TechnicianCreate,
    current_user: DispatcherUser,
    db: DbSession,
) -> TechnicianOut:
    """Create a technician."""
    tech = Technician(**body.model_dump())
    db.add(tech)
    db.commit()
    db.refresh(tech)
    return TechnicianOut.model_validate(tech)


@router.put("/api/v1/technicians/{id}", response_model=TechnicianOut)
def update_technician(
    id: str,
    body: TechnicianUpdate,
    current_user: DispatcherUser,
    db: DbSession,
) -> TechnicianOut:
    """Update a technician."""
    tech = db.get(Technician, id)
    if not tech:
        raise HTTPException(status_code=404, detail="Technician not found")
    updates = body.model_dump(exclude_unset=True)
    for k, v in updates.items():
        setattr(tech, k, v)
    db.commit()
    db.refresh(tech)
    return TechnicianOut.model_validate(tech)
