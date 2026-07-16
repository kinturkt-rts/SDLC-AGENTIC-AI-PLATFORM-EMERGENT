"""Work orders router — includes status, addendum, and audit-log."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.dependencies import AuthUser, DbSession, DispatcherUser
from app.models.assignment import Assignment
from app.models.audit_log import AuditLog
from app.models.part_line_item import PartLineItem
from app.models.work_order import WorkOrder
from schemas.audit_log import AuditLogOut
from schemas.work_order import AddendumUpdate, StatusUpdate, WorkOrderCreate, WorkOrderOut

router = APIRouter()

_ALLOWED_TRANSITIONS = {
    "new": ["assigned", "cancelled"],
    "assigned": ["in_progress", "cancelled"],
    "in_progress": ["completed", "cancelled"],
}


@router.get("/api/v1/work-orders", response_model=list[WorkOrderOut])
def list_work_orders(
    current_user: AuthUser,
    db: DbSession,
    date_filter: Optional[date] = Query(default=None, alias="date"),
) -> list[WorkOrderOut]:
    """List work orders. Technicians see only their own."""
    stmt = select(WorkOrder)
    if date_filter:
        stmt = stmt.where(WorkOrder.scheduled_date == date_filter)
    if current_user.role == "technician":
        stmt = stmt.join(Assignment, Assignment.work_order_id == WorkOrder.id).where(
            Assignment.technician_id == current_user.technician_id,
            Assignment.is_active.is_(True),
        )
    rows = db.scalars(stmt.order_by(WorkOrder.created_at.desc())).all()
    return [WorkOrderOut.model_validate(r) for r in rows]


@router.post("/api/v1/work-orders", response_model=WorkOrderOut, status_code=201)
def create_work_order(
    body: WorkOrderCreate,
    current_user: DispatcherUser,
    db: DbSession,
) -> WorkOrderOut:
    """Create a new work order (dispatcher only)."""
    if body.priority not in ("routine", "urgent"):
        raise HTTPException(status_code=422, detail="priority must be 'routine' or 'urgent'")
    if body.time_window not in ("morning", "afternoon", "all_day"):
        raise HTTPException(status_code=422, detail="time_window must be 'morning', 'afternoon', or 'all_day'")
    wo = WorkOrder(**body.model_dump())
    db.add(wo)
    db.commit()
    db.refresh(wo)
    return WorkOrderOut.model_validate(wo)


@router.patch("/api/v1/work-orders/{id}/status", response_model=WorkOrderOut)
def update_status(
    id: str,
    body: StatusUpdate,
    current_user: AuthUser,
    db: DbSession,
) -> WorkOrderOut:
    """Advance work order status (state machine + RBAC)."""
    wo = db.get(WorkOrder, id)
    if not wo:
        raise HTTPException(status_code=404, detail="Work order not found")

    from_status = wo.status
    to_status = body.status

    if current_user.role == "owner":
        raise HTTPException(status_code=403, detail="Forbidden")

    if from_status in ("completed", "cancelled"):
        raise HTTPException(status_code=422, detail="Work order is in a terminal state")

    allowed = _ALLOWED_TRANSITIONS.get(from_status, [])
    if to_status not in allowed:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot transition from '{from_status}' to '{to_status}'",
        )

    if current_user.role == "technician":
        assignment = db.scalars(
            select(Assignment).where(
                Assignment.work_order_id == id,
                Assignment.is_active.is_(True),
            )
        ).first()
        if not assignment or assignment.technician_id != current_user.technician_id:
            raise HTTPException(status_code=403, detail="Forbidden")
        if to_status not in ("in_progress", "completed"):
            raise HTTPException(status_code=403, detail="Forbidden")

    if to_status == "completed":
        notes = (body.completion_notes or "").strip()
        if not notes:
            raise HTTPException(status_code=422, detail="completion_notes required for completion")
        wo.completion_notes = notes
        if body.parts:
            for p in body.parts:
                part = PartLineItem(
                    work_order_id=id,
                    name=p.name,
                    quantity=p.quantity,
                    unit_cost=p.unit_cost,
                )
                db.add(part)

    wo.status = to_status
    wo.updated_at = datetime.now(timezone.utc)

    audit = AuditLog(
        work_order_id=id,
        from_status=from_status,
        to_status=to_status,
        actor_id=current_user.user_id,
        actor_role=current_user.role,
    )
    db.add(audit)
    db.commit()
    db.refresh(wo)
    return WorkOrderOut.model_validate(wo)


@router.patch("/api/v1/work-orders/{id}/addendum", response_model=WorkOrderOut)
def update_addendum(
    id: str,
    body: AddendumUpdate,
    current_user: DispatcherUser,
    db: DbSession,
) -> WorkOrderOut:
    """Dispatcher can add addendum to completed orders."""
    wo = db.get(WorkOrder, id)
    if not wo:
        raise HTTPException(status_code=404, detail="Work order not found")
    if wo.status != "completed":
        raise HTTPException(status_code=422, detail="Addendum only allowed on completed orders")
    wo.dispatcher_addendum = body.dispatcher_addendum
    wo.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(wo)
    return WorkOrderOut.model_validate(wo)


@router.get("/api/v1/work-orders/{id}/audit-log", response_model=list[AuditLogOut])
def get_audit_log(
    id: str,
    current_user: AuthUser,
    db: DbSession,
) -> list[AuditLogOut]:
    """Get audit log for a work order. Dispatcher+Owner only."""
    if current_user.role == "technician":
        raise HTTPException(status_code=403, detail="Forbidden")

    entries = db.scalars(
        select(AuditLog)
        .where(AuditLog.work_order_id == id)
        .order_by(AuditLog.changed_at)
    ).all()
    return [AuditLogOut.model_validate(e) for e in entries]
