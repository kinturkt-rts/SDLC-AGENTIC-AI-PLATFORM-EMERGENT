"""Blackout windows router."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.dependencies import AuthUser, DbSession, ManagerUser
from app.models.blackout_window import BlackoutWindow
from app.models.environment import Environment
from schemas.blackout_window import BlackoutWindowCreate, BlackoutWindowListPage, BlackoutWindowOut

router = APIRouter()


@router.get("/api/v1/blackout-windows", response_model=BlackoutWindowListPage)
def list_blackout_windows(
    db: DbSession,
    current_user: AuthUser,
    environment_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> BlackoutWindowListPage:
    stmt = select(BlackoutWindow)
    count_stmt = select(func.count(BlackoutWindow.id))
    if environment_id:
        stmt = stmt.where(BlackoutWindow.environment_id == environment_id)
        count_stmt = count_stmt.where(BlackoutWindow.environment_id == environment_id)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.order_by(BlackoutWindow.start_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return BlackoutWindowListPage(items=rows, total=total, page=page, page_size=page_size)


@router.post("/api/v1/blackout-windows", response_model=BlackoutWindowOut, status_code=status.HTTP_201_CREATED)
def create_blackout_window(
    body: BlackoutWindowCreate,
    db: DbSession,
    current_user: ManagerUser,
) -> BlackoutWindowOut:
    # Validate environment exists
    env = db.scalars(select(Environment).where(Environment.id == body.environment_id)).first()
    if not env:
        raise HTTPException(status_code=422, detail="Environment not found")
    bw = BlackoutWindow(
        environment_id=body.environment_id,
        start_at=body.start_at,
        end_at=body.end_at,
        reason=body.reason,
        created_by=current_user.user_id,
    )
    db.add(bw)
    db.commit()
    db.refresh(bw)
    return bw  # type: ignore[return-value]
