"""Dashboard router — GET /api/v1/dashboard/summary."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter
from sqlalchemy import func, select

from app.dependencies import DashboardUser, DbSession
from app.models.change_request import ChangeRequest
from schemas.dashboard import DashboardSummary

router = APIRouter()

_TERMINAL_STATUSES = ("completed", "closed", "rejected")


@router.get("/api/v1/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(
    db: DbSession,
    current_user: DashboardUser,
) -> DashboardSummary:
    """Aggregated dashboard metrics."""
    # counts by status
    status_rows = db.execute(
        select(ChangeRequest.status, func.count(ChangeRequest.id))
        .group_by(ChangeRequest.status)
    ).all()
    counts_by_status = {row[0]: row[1] for row in status_rows}

    # counts by risk
    risk_rows = db.execute(
        select(ChangeRequest.risk, func.count(ChangeRequest.id))
        .group_by(ChangeRequest.risk)
    ).all()
    counts_by_risk = {row[0]: row[1] for row in risk_rows}

    # overdue scheduled
    now = datetime.now(timezone.utc)
    overdue_count = db.scalar(
        select(func.count(ChangeRequest.id)).where(
            ChangeRequest.status.notin_(_TERMINAL_STATUSES),
            ChangeRequest.planned_end < now,
        )
    ) or 0

    # monthly by environment (current month)
    monthly_rows = db.execute(
        select(
            ChangeRequest.target_environment_id,
            func.count(ChangeRequest.id),
        )
        .where(
            func.extract("year", ChangeRequest.created_at) == now.year,
            func.extract("month", ChangeRequest.created_at) == now.month,
        )
        .group_by(ChangeRequest.target_environment_id)
    ).all()
    monthly_by_env = [{"environment_id": str(row[0]), "count": row[1]} for row in monthly_rows]

    # top services by volume
    top_rows = db.execute(
        select(ChangeRequest.service_id, func.count(ChangeRequest.id).label("cnt"))
        .group_by(ChangeRequest.service_id)
        .order_by(func.count(ChangeRequest.id).desc())
        .limit(10)
    ).all()
    top_services = [{"service_id": str(row[0]), "count": row[1]} for row in top_rows]

    # active emergency count
    emergency_count = db.scalar(
        select(func.count(ChangeRequest.id)).where(
            ChangeRequest.change_type == "emergency",
            ChangeRequest.status.notin_(_TERMINAL_STATUSES),
        )
    ) or 0

    return DashboardSummary(
        counts_by_status=counts_by_status,
        counts_by_risk=counts_by_risk,
        overdue_scheduled_count=overdue_count,
        monthly_by_env=monthly_by_env,
        top_services=top_services,
        active_emergency_count=emergency_count,
    )
