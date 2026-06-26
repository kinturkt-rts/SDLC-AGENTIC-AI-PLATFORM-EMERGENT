"""Board and Workload routers."""
from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.dependencies import CurrentUser
from app.models.technician import Technician
from app.models.work_order import WorkOrder
from schemas.board import BoardResponse, TechnicianWorkload, WorkloadResponse
from schemas.work_order import WorkOrderOut

router = APIRouter(tags=["board"])


def _is_sla_breached(wo: WorkOrder, sla_hour: int) -> bool:
    """Urgent order past scheduled_date + breach hour and not completed/cancelled."""
    if wo.priority != "urgent":
        return False
    if wo.status in ("completed", "cancelled"):
        return False
    today = date.today()
    if wo.scheduled_date > today:
        return False
    if wo.scheduled_date < today:
        return True
    # Scheduled today — only breached after sla_hour
    now_hour = datetime.now(timezone.utc).hour
    return now_hour >= sla_hour


@router.get("/board", response_model=BoardResponse)
def get_board(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    board_date: date = Query(default=None, alias="date"),
) -> BoardResponse:
    """Today's dispatch board — unassigned, technician columns, SLA breaches."""
    settings = get_settings()
    target_date = board_date or date.today()

    # Get all work orders for the date (plus overdue urgents)
    all_orders = (
        db.query(WorkOrder)
        .filter(
            WorkOrder.scheduled_date <= target_date,
            WorkOrder.status.notin_(["completed", "cancelled"]),
        )
        .all()
    )
    # Also include completed/cancelled for target_date to show in tech columns
    date_orders = (
        db.query(WorkOrder)
        .filter(WorkOrder.scheduled_date == target_date)
        .all()
    )

    # Combine, deduplicate
    seen_ids: set[str] = set()
    combined: list[WorkOrder] = []
    for wo in list(all_orders) + list(date_orders):
        if wo.id not in seen_ids:
            seen_ids.add(wo.id)
            combined.append(wo)

    unassigned: list[WorkOrder] = []
    tech_columns: dict[str, list[WorkOrder]] = {}
    sla_breaches: list[WorkOrder] = []

    for wo in combined:
        # SLA breach check
        if _is_sla_breached(wo, settings.sla_breach_hour):
            sla_breaches.append(wo)

        # If technician role, filter to own orders only
        if current_user.role == "technician":
            if wo.assigned_technician_id != current_user.technician_id:
                continue

        if wo.assigned_technician_id is None:
            unassigned.append(wo)
        else:
            tech_id = str(wo.assigned_technician_id)
            tech_columns.setdefault(tech_id, []).append(wo)

    return BoardResponse(
        unassigned=[WorkOrderOut.model_validate(wo) for wo in unassigned],
        technician_columns={k: [WorkOrderOut.model_validate(wo) for wo in v] for k, v in tech_columns.items()},
        sla_breaches=[WorkOrderOut.model_validate(wo) for wo in sla_breaches],
    )


@router.get("/workload", response_model=WorkloadResponse)
def get_workload(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    workload_date: date = Query(default=None, alias="date"),
) -> WorkloadResponse:
    """Workload summary per active technician for a given date."""
    # Owner + Dispatcher only
    if current_user.role == "technician":
        from fastapi import HTTPException, status as http_status
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="Forbidden")

    settings = get_settings()
    target_date = workload_date or date.today()

    techs = db.query(Technician).filter(Technician.is_active == True).all()  # noqa: E712

    result: list[TechnicianWorkload] = []
    for tech in techs:
        orders = (
            db.query(WorkOrder)
            .filter(
                WorkOrder.assigned_technician_id == tech.id,
                WorkOrder.scheduled_date == target_date,
            )
            .all()
        )
        total = len(orders)
        in_progress = sum(1 for o in orders if o.status == "in_progress")
        completed = sum(1 for o in orders if o.status == "completed")
        breach = any(_is_sla_breached(o, settings.sla_breach_hour) for o in orders)

        result.append(
            TechnicianWorkload(
                technician_id=str(tech.id),
                display_name=tech.display_name,
                total_assigned=total,
                in_progress_count=in_progress,
                completed_count=completed,
                sla_breach_flag=breach,
            )
        )

    return WorkloadResponse(workload=result)
