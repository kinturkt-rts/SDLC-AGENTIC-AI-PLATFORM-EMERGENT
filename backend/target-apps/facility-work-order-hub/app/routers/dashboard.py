"""Dashboard router — SLA and workload views."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.dependencies import AdminUser, AdminOrLeadership, DbSession
from app.models.user import User
from app.models.work_order import WorkOrder
from schemas.dashboard import SLADashboard, TechnicianWorkload

router = APIRouter()


@router.get("/sla", response_model=SLADashboard)
def sla_dashboard(db: DbSession, current_user: AdminOrLeadership) -> SLADashboard:
    now = datetime.now(timezone.utc)
    # Current month boundaries
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Open count (not closed)
    open_count = db.scalar(
        select(func.count(WorkOrder.id)).where(WorkOrder.status != "closed")
    ) or 0

    # Closed this month
    closed_count = db.scalar(
        select(func.count(WorkOrder.id)).where(
            WorkOrder.status == "closed",
            WorkOrder.closed_at >= month_start,
        )
    ) or 0

    # Overdue count
    overdue_count = db.scalar(
        select(func.count(WorkOrder.id)).where(
            WorkOrder.due_by.isnot(None),
            WorkOrder.due_by < now,
            WorkOrder.status != "closed",
        )
    ) or 0

    # Avg days to close by category
    closed_orders = list(db.scalars(
        select(WorkOrder).where(
            WorkOrder.status == "closed",
            WorkOrder.closed_at.isnot(None),
        )
    ).all())

    cat_days: dict[str, list[float]] = {}
    for wo in closed_orders:
        if wo.closed_at and wo.created_at:
            try:
                delta = (wo.closed_at - wo.created_at).total_seconds() / 86400.0
                cat_days.setdefault(wo.category, []).append(delta)
            except (TypeError, AttributeError):
                pass

    avg_days_to_close_by_category = {
        cat: round(sum(days) / len(days), 1) for cat, days in cat_days.items() if days
    }

    # Top sites by volume
    site_counts = db.execute(
        select(WorkOrder.site_id, func.count(WorkOrder.id).label("count"))
        .group_by(WorkOrder.site_id)
        .order_by(func.count(WorkOrder.id).desc())
        .limit(5)
    ).all()
    top_sites = [{"site_id": str(row[0]), "count": row[1]} for row in site_counts]

    return SLADashboard(
        open_count=open_count,
        closed_count=closed_count,
        overdue_count=overdue_count,
        avg_days_to_close_by_category=avg_days_to_close_by_category,
        top_sites=top_sites,
    )


@router.get("/workload", response_model=list[TechnicianWorkload])
def workload_dashboard(db: DbSession, current_user: AdminUser) -> list[TechnicianWorkload]:
    # Get technicians with open work orders (assigned or in_progress)
    results = db.execute(
        select(
            WorkOrder.assignee_id,
            func.count(WorkOrder.id).label("open_count"),
        )
        .where(
            WorkOrder.assignee_id.isnot(None),
            WorkOrder.status.in_(["assigned", "in_progress"]),
        )
        .group_by(WorkOrder.assignee_id)
    ).all()

    workload: list[TechnicianWorkload] = []
    for row in results:
        tech = db.scalars(select(User).where(User.id == row[0])).first()
        if tech:
            workload.append(TechnicianWorkload(
                technician_id=str(tech.id),
                display_name=tech.display_name,
                open_count=row[1],
            ))
    return workload
