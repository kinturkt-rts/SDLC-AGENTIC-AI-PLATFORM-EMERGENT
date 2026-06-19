"""Work Orders router — create, patch (assign/status/complete/addendum), history."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import CurrentUser, DispatcherUser
from app.models.status_history import StatusHistory
from app.models.technician import Technician
from app.models.work_order import WorkOrder, WorkOrderPart
from schemas.history import HistoryEntry
from schemas.work_order import WorkOrderCreate, WorkOrderOut, WorkOrderPatch

router = APIRouter(tags=["work-orders"])


def _record_history(
    db: Session,
    work_order_id: str,
    actor_user_id: str,
    actor_role: str,
    previous_status: str | None,
    new_status: str,
    context_note: str | None = None,
) -> None:
    entry = StatusHistory(
        work_order_id=work_order_id,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        previous_status=previous_status,
        new_status=new_status,
        context_note=context_note,
    )
    db.add(entry)


@router.post("", response_model=WorkOrderOut, status_code=201)
def create_work_order(
    body: WorkOrderCreate,
    current_user: DispatcherUser,
    db: Session = Depends(get_db),
) -> WorkOrderOut:
    """Create a work order. Dispatcher only."""
    # Validate priority
    if body.priority not in ("routine", "urgent"):
        raise HTTPException(status_code=422, detail="Priority must be 'routine' or 'urgent'")
    if body.time_window not in ("morning", "afternoon", "all_day"):
        raise HTTPException(status_code=422, detail="time_window must be morning, afternoon, or all_day")

    wo = WorkOrder(
        customer_id=body.customer_id,
        description=body.description,
        priority=body.priority,
        scheduled_date=body.scheduled_date,
        time_window=body.time_window,
        status="new",
    )
    db.add(wo)
    db.flush()

    _record_history(db, wo.id, current_user.id, current_user.role, None, "new", "Work order created")
    db.commit()
    db.refresh(wo)
    return wo  # type: ignore[return-value]


@router.get("/{work_order_id}", response_model=WorkOrderOut)
def get_work_order(
    work_order_id: str,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> WorkOrderOut:
    """Get a single work order by ID."""
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="Work order not found")
    return wo  # type: ignore[return-value]


@router.patch("/{work_order_id}", response_model=WorkOrderOut)
def patch_work_order(
    work_order_id: str,
    body: WorkOrderPatch,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> WorkOrderOut:
    """
    Patch a work order — handles assignment, status transitions, completion, addendum.
    Business rules enforced per design §5.
    """
    # Owner cannot mutate
    if current_user.role == "owner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="Work order not found")

    # ── Completion lock — completed orders only accept addendum ──
    if wo.status == "completed":
        if body.addendum:
            # Only dispatcher can add addendum
            if current_user.role != "dispatcher":
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
            timestamp_prefix = datetime.now(timezone.utc).strftime("[%Y-%m-%d %H:%M UTC] ")
            wo.completion_notes = (wo.completion_notes or "") + "\n" + timestamp_prefix + body.addendum
            _record_history(db, wo.id, current_user.id, current_user.role, "completed", "completed", f"Addendum: {body.addendum}")
            db.commit()
            db.refresh(wo)
            return wo  # type: ignore[return-value]
        # Any other field change on completed → 409
        if body.status or body.assigned_technician_id or body.completion_notes or body.parts:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Completed orders cannot be modified except by addendum")
        db.refresh(wo)
        return wo  # type: ignore[return-value]

    # ── Technician role guards — own assignments only ──
    if current_user.role == "technician":
        if wo.assigned_technician_id != current_user.technician_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        # Technicians can only change status
        if body.assigned_technician_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    # ── Assignment ──
    if body.assigned_technician_id:
        if current_user.role != "dispatcher":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        if wo.status not in ("new", "assigned"):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot assign — order not in assignable state")
        tech = db.query(Technician).filter(Technician.id == body.assigned_technician_id).first()
        if not tech:
            raise HTTPException(status_code=422, detail="Technician not found")
        if not tech.is_active:
            raise HTTPException(status_code=422, detail="Technician is not active")

        old_status = wo.status
        wo.assigned_technician_id = body.assigned_technician_id
        wo.status = "assigned"
        context = f"Assigned to {tech.display_name}"
        _record_history(db, wo.id, current_user.id, current_user.role, old_status, "assigned", context)

    # ── Status transition (explicit) ──
    if body.status and body.status != wo.status:
        new_status = body.status
        old_status = wo.status

        # Validate transition
        valid_transitions: dict[str, set[str]] = {
            "new": {"assigned", "cancelled"},
            "assigned": {"in_progress", "cancelled"},
            "in_progress": {"completed", "cancelled"},
        }
        allowed = valid_transitions.get(old_status, set())
        if new_status not in allowed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Invalid transition from '{old_status}' to '{new_status}'",
            )

        # Technician can only do assigned->in_progress, in_progress->completed
        if current_user.role == "technician":
            tech_allowed = {
                "assigned": {"in_progress"},
                "in_progress": {"completed"},
            }
            if new_status not in tech_allowed.get(old_status, set()):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

        # Cancel not allowed on completed (already handled above)
        if new_status == "cancelled" and current_user.role != "dispatcher":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

        # Completion requires notes
        if new_status == "completed":
            notes = body.completion_notes
            if not notes or not notes.strip():
                raise HTTPException(status_code=422, detail="Completion notes are required")
            wo.completion_notes = notes

        wo.status = new_status
        _record_history(db, wo.id, current_user.id, current_user.role, old_status, new_status, body.completion_notes if new_status == "completed" else None)

    # ── Parts (on completion or addendum) ──
    if body.parts:
        for p in body.parts:
            part = WorkOrderPart(
                work_order_id=wo.id,
                part_name=p.part_name,
                quantity=p.quantity,
                unit_cost=p.unit_cost,
            )
            db.add(part)

    db.commit()
    db.refresh(wo)
    return wo  # type: ignore[return-value]


@router.get("/{work_order_id}/history", response_model=list[HistoryEntry])
def get_work_order_history(
    work_order_id: str,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> list[HistoryEntry]:
    """Get the status-change audit history for a work order."""
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="Work order not found")
    entries = (
        db.query(StatusHistory)
        .filter(StatusHistory.work_order_id == work_order_id)
        .order_by(StatusHistory.changed_at)
        .all()
    )
    return list(entries)  # type: ignore[return-value]
