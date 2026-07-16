"""Board router — dispatch board view."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.config import get_settings
from app.dependencies import DbSession, DispatcherOrOwner
from app.models.assignment import Assignment
from app.models.technician import Technician
from app.models.work_order import WorkOrder
from schemas.board import BoardResponse, BoardWorkOrder, TechnicianColumn
from schemas.work_order import WorkOrderOut

router = APIRouter()


def _is_sla_breached(wo: WorkOrder, target_date: date) -> bool:
    """Check if an urgent order is SLA-breached."""
    if wo.priority != "urgent":
        return False
    if wo.status in ("completed", "cancelled"):
        return False
    if wo.scheduled_date > target_date:
        return False
    today = date.today()
    if wo.scheduled_date < today:
        return True
    settings = get_settings()
    now = datetime.now(timezone.utc)
    if now.hour >= settings.sla_cutoff_hour:
        return True
    return False


@router.get("/api/v1/board", response_model=BoardResponse)
def get_board(
    current_user: DispatcherOrOwner,
    db: DbSession,
    board_date: Optional[date] = Query(default=None, alias="date"),
) -> BoardResponse:
    """Get dispatch board for a given date (default: today)."""
    target_date = board_date or date.today()

    orders = db.scalars(
        select(WorkOrder).where(WorkOrder.scheduled_date == target_date)
    ).all()

    active_techs = db.scalars(
        select(Technician).where(Technician.active.is_(True)).order_by(Technician.name)
    ).all()

    unassigned: list[BoardWorkOrder] = []
    tech_orders: dict[str, list[BoardWorkOrder]] = {t.id: [] for t in active_techs}
    sla_breaches: list[BoardWorkOrder] = []

    for wo in orders:
        breached = _is_sla_breached(wo, target_date)
        assignment = db.scalars(
            select(Assignment).where(
                Assignment.work_order_id == wo.id,
                Assignment.is_active.is_(True),
            )
        ).first()

        tech_name: str | None = None
        if assignment:
            tech = db.get(Technician, assignment.technician_id)
            tech_name = tech.name if tech else None

        board_wo = BoardWorkOrder(
            **WorkOrderOut.model_validate(wo).model_dump(),
            sla_breached=breached,
            technician_name=tech_name,
        )

        if not assignment or not assignment.is_active:
            unassigned.append(board_wo)
        else:
            tech_id = assignment.technician_id
            if tech_id in tech_orders:
                tech_orders[tech_id].append(board_wo)
            else:
                unassigned.append(board_wo)

        if breached:
            sla_breaches.append(board_wo)

    tech_columns = [
        TechnicianColumn(
            technician_id=str(t.id),
            technician_name=t.name,
            orders=tech_orders.get(t.id, []),
        )
        for t in active_techs
    ]

    return BoardResponse(
        unassigned=unassigned,
        technicians=tech_columns,
        sla_breaches=sla_breaches,
    )
