"""Service catalog CRUD — Admin only."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.dependencies import AdminRole, DbSession
from app.models.service import Service
from schemas.services import ServiceCreate, ServiceListPage, ServiceOut, ServiceUpdate

router = APIRouter(tags=["services"])


@router.get("/api/v1/services", response_model=ServiceListPage)
def list_services(
    db: DbSession,
    _role: AdminRole,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    total = db.scalar(select(func.count(Service.id))) or 0
    rows = db.scalars(select(Service).offset(offset).limit(limit)).all()
    return ServiceListPage(items=rows, total=total, limit=limit, offset=offset)


@router.get("/api/v1/services/{id}", response_model=ServiceOut)
def get_service(id: str, db: DbSession, _role: AdminRole):
    svc = db.get(Service, id)
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")
    return svc


@router.post("/api/v1/services", response_model=ServiceOut, status_code=status.HTTP_201_CREATED)
def create_service(body: ServiceCreate, db: DbSession, _role: AdminRole):
    svc = Service(
        name=body.name,
        owning_team=body.owning_team,
        criticality_tier=body.criticality_tier,
        active_support=body.active_support,
    )
    db.add(svc)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Service name already exists")
    db.refresh(svc)
    return svc


@router.put("/api/v1/services/{id}", response_model=ServiceOut)
def update_service(id: str, body: ServiceUpdate, db: DbSession, _role: AdminRole):
    svc = db.get(Service, id)
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")
    updates = body.model_dump(exclude_unset=True)
    for k, v in updates.items():
        setattr(svc, k, v)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Service name already exists")
    db.refresh(svc)
    return svc


@router.delete("/api/v1/services/{id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_service(id: str, db: DbSession, _role: AdminRole):
    svc = db.get(Service, id)
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")
    db.delete(svc)
    db.commit()
    return None
