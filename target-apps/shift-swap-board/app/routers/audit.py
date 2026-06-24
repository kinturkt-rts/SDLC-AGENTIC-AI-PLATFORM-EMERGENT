"""Audit router — GET /audit (admin only)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.dependencies import AuthUser, DbSession
from app.models.swap_audit_log import SwapAuditLog
from schemas.swap import AuditRow

router = APIRouter()


@router.get("/audit", response_model=list[AuditRow])
def list_audit(
    db: DbSession,
    current_user: AuthUser,
    limit: int = Query(default=50, ge=1, le=500),
) -> list[AuditRow]:
    """List recent audit entries (admin only)."""
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")

    rows = db.scalars(
        select(SwapAuditLog).order_by(SwapAuditLog.created_at.desc()).limit(limit)
    ).all()
    return [AuditRow.model_validate(r) for r in rows]
