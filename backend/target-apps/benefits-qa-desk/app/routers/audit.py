"""Audit trail router — admin only."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import AdminUser
from app.models.audit_event import AuditEvent
from schemas.audit import AuditEventOut, AuditListResponse

router = APIRouter()


@router.get("/api/v1/audit", response_model=AuditListResponse)
def list_audit_events(
    current_user: AdminUser,
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    action_type: str | None = Query(default=None),
    from_date: str | None = Query(default=None),
    to_date: str | None = Query(default=None),
) -> AuditListResponse:
    stmt = select(AuditEvent)
    count_stmt = select(func.count(AuditEvent.id))

    if action_type:
        stmt = stmt.where(AuditEvent.action_type == action_type)
        count_stmt = count_stmt.where(AuditEvent.action_type == action_type)
    if from_date:
        stmt = stmt.where(AuditEvent.timestamp >= from_date)
        count_stmt = count_stmt.where(AuditEvent.timestamp >= from_date)
    if to_date:
        stmt = stmt.where(AuditEvent.timestamp <= to_date)
        count_stmt = count_stmt.where(AuditEvent.timestamp <= to_date)

    total = db.scalar(count_stmt) or 0
    offset = (page - 1) * page_size
    rows = db.scalars(stmt.order_by(AuditEvent.timestamp.desc()).offset(offset).limit(page_size)).all()
    items = [AuditEventOut.model_validate(r) for r in rows]
    return AuditListResponse(items=items, total=total)
