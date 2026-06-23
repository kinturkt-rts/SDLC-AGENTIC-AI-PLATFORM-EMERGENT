"""Environments router."""
from __future__ import annotations

from fastapi import APIRouter, Query, status
from sqlalchemy import func, select

from app.dependencies import AuthUser, DbSession, ManagerUser
from app.models.environment import Environment
from schemas.environment import EnvironmentCreate, EnvironmentListPage, EnvironmentOut

router = APIRouter()


@router.get("/api/v1/environments", response_model=EnvironmentListPage)
def list_environments(
    db: DbSession,
    current_user: AuthUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> EnvironmentListPage:
    total = db.scalar(select(func.count(Environment.id))) or 0
    rows = db.scalars(select(Environment).order_by(Environment.sort_order).offset((page - 1) * page_size).limit(page_size)).all()
    return EnvironmentListPage(items=rows, total=total, page=page, page_size=page_size)


@router.post("/api/v1/environments", response_model=EnvironmentOut, status_code=status.HTTP_201_CREATED)
def create_environment(
    body: EnvironmentCreate,
    db: DbSession,
    current_user: ManagerUser,
) -> EnvironmentOut:
    env = Environment(name=body.name, sort_order=body.sort_order)
    db.add(env)
    db.commit()
    db.refresh(env)
    return env  # type: ignore[return-value]
