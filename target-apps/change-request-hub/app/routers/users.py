"""Users router — GET /api/v1/users."""
from __future__ import annotations

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.dependencies import AuthUser, DbSession
from app.models.user import User
from schemas.user import UserListPage

router = APIRouter()


@router.get("/api/v1/users", response_model=UserListPage)
def list_users(
    db: DbSession,
    current_user: AuthUser,
    role: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> UserListPage:
    """List users, optionally filtered by role."""
    stmt = select(User).where(User.active == True)  # noqa: E712
    count_stmt = select(func.count(User.id)).where(User.active == True)  # noqa: E712
    if role:
        stmt = stmt.where(User.role == role)
        count_stmt = count_stmt.where(User.role == role)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.order_by(User.display_name).offset((page - 1) * page_size).limit(page_size)).all()
    return UserListPage(items=rows, total=total, page=page, page_size=page_size)
