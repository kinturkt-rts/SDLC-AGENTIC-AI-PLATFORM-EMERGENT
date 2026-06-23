"""Services router — CRUD for service catalog."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.dependencies import AuthUser, DbSession, ManagerUser
from app.models.service import Service
from schemas.service import ServiceCreate, ServiceListPage, ServiceOut, ServiceUpdate

router = APIRouter()


@router.get("/api/v1/services", response_model=ServiceListPage)
def list_services(
    db: DbSession,
    current_user: AuthUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    active: bool | None = Query(default=None),
) -> ServiceListPage:
    stmt = select(Service)
    count_stmt = select(func.count(Service.id))
    if active is not None:
        stmt = stmt.where(Service.active == active)
        count_stmt = count_stmt.where(Service.active == active)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.order_by(Service.name).offset((page - 1) * page_size).limit(page_size)).all()
    return ServiceListPage(items=rows, total=total, page=page, page_size=page_size)


@router.post("/api/v1/services", response_model=ServiceOut, status_code=status.HTTP_201_CREATED)
def create_service(
    body: ServiceCreate,
    db: DbSession,
    current_user: ManagerUser,
) -> ServiceOut:
    if body.tier not in ("tier1", "tier2", "tier3"):
        raise HTTPException(status_code=422, detail="Invalid tier value")
    svc = Service(name=body.name, owner_team=body.owner_team, tier=body.tier)
    db.add(svc)
    db.commit()
    db.refresh(svc)
    return svc  # type: ignore[return-value]


@router.patch("/api/v1/services/{id}", response_model=ServiceOut)
def update_service(
    id: str,
    body: ServiceUpdate,
    db: DbSession,
    current_user: ManagerUser,
) -> ServiceOut:
    svc = db.scalars(select(Service).where(Service.id == id)).first()
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")
    updates = body.model_dump(exclude_unset=True)
    if "tier" in updates and updates["tier"] not in ("tier1", "tier2", "tier3"):
        raise HTTPException(status_code=422, detail="Invalid tier value")
    for k, v in updates.items():
        setattr(svc, k, v)
    svc.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(svc)
    return svc  # type: ignore[return-value]
