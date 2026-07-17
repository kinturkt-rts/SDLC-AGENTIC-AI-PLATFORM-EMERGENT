"""Assignments router."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.dependencies import AuthUser, DbSession, DispatcherUser
from app.models.assignment import Assignment
from app.models.audit_log import AuditLog
from app.models.technician import Technician
from app.models.work_order import WorkOrder
from schemas.assignment import AssignmentCreate, AssignmentOut

router = APIRouter()


@router.get("/api/v1/assignments", response_model=list[AssignmentOut])
def list_assignments(
    current_user: AuthUser,
    db: DbSession,
) -> list[AssignmentOut]:
    """List all active assignments."""
    rows = db.scalars(
        select(Assignment).where(Assignment.is_active.is_(True))
    ).all()
    return [AssignmentOut.model_validate(r) for r in rows]


@router.post("/api/v1/assignments", response_model=AssignmentOut, status_code=201)
def create_assignment(
    body: AssignmentCreate,
    current_user: DispatcherUser,
    db: DbSession,
) -> AssignmentOut:
    """Assign a technician to a work order (dispatcher only)."""
    wo = db.get(WorkOrder, body.work_order_id)
    if not wo:
        raise HTTPException(status_code=404, detail="Work order not found")

    if wo.status not in ("new", "assigned"):
        raise HTTPException(status_code=422, detail="Work order is not in a dispatchable state")

    tech = db.get(Technician, body.technician_id)
    if not tech:
        raise HTTPException(status_code=404, detail="Technician not found")
    if not tech.active:
        raise HTTPException(status_code=422, detail="Technician is inactive")

    existing = db.scalars(
        select(Assignment).where(
            Assignment.work_order_id == body.work_order_id,
            Assignment.is_active.is_(True),
        )
    ).first()

    if existing:
        if wo.status == "assigned":
            existing.is_active = False
        else:
            raise HTTPException(status_code=409, detail="Active assignment already exists")

    assignment = Assignment(
        work_order_id=body.work_order_id,
        technician_id=body.technician_id,
        assigned_by=current_user.user_id,
    )
    db.add(assignment)

    from_status = wo.status
    if wo.status == "new":
        wo.status = "assigned"

    if from_status != wo.status:
        audit = AuditLog(
            work_order_id=body.work_order_id,
            from_status=from_status,
            to_status=wo.status,
            actor_id=current_user.user_id,
            actor_role=current_user.role,
        )
        db.add(audit)

    db.commit()
    db.refresh(assignment)
    return AssignmentOut.model_validate(assignment)
