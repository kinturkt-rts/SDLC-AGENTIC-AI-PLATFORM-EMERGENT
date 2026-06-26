"""Work orders router — CRUD + status lifecycle."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.dependencies import AdminUser, AuthUser, DbSession
from app.models.site import Site
from app.models.user import User
from app.models.work_order import WorkOrder
from app.models.status_history import WorkOrderStatusHistory
from schemas.work_order import (
    AssignRequest,
    StatusUpdateRequest,
    WorkOrderCreate,
    WorkOrderListPage,
    WorkOrderOut,
)

router = APIRouter()

# Valid transitions: from -> set of allowed targets
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "submitted": {"triaged"},
    "triaged": {"assigned"},
    "assigned": {"in_progress"},
    "in_progress": {"completed"},
    "completed": {"closed"},
    "closed": {"in_progress"},  # reopen
}


def _compute_overdue(wo: WorkOrder) -> bool:
    if wo.due_by is None:
        return False
    if wo.status == "closed":
        return False
    now = datetime.now(timezone.utc)
    due = wo.due_by
    # Handle naive datetime (SQLite stores naive) — assume UTC
    if hasattr(due, 'tzinfo') and due.tzinfo is None:
        due = due.replace(tzinfo=timezone.utc)
    try:
        return due < now
    except TypeError:
        return False


def _wo_to_out(wo: WorkOrder, warnings: list[str] | None = None) -> WorkOrderOut:
    return WorkOrderOut(
        id=str(wo.id),
        title=wo.title,
        description=wo.description,
        category=wo.category,
        priority=wo.priority,
        status=wo.status,
        requester_id=str(wo.requester_id),
        assignee_id=str(wo.assignee_id) if wo.assignee_id else None,
        site_id=str(wo.site_id),
        location_id=str(wo.location_id) if wo.location_id else None,
        due_by=wo.due_by,
        reopen_reason=wo.reopen_reason,
        created_at=wo.created_at,
        updated_at=wo.updated_at,
        assigned_at=wo.assigned_at,
        started_at=wo.started_at,
        completed_at=wo.completed_at,
        closed_at=wo.closed_at,
        is_overdue=_compute_overdue(wo),
        warnings=warnings,
    )


@router.post("", response_model=WorkOrderOut, status_code=status.HTTP_201_CREATED)
def create_work_order(body: WorkOrderCreate, db: DbSession, current_user: AuthUser) -> WorkOrderOut:
    if current_user.role not in ("requester", "facilities_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only requesters or admins can create work orders")

    # Validate category
    valid_categories = {"HVAC", "plumbing", "electrical", "access", "general"}
    if body.category not in valid_categories:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Invalid category. Must be one of: {valid_categories}")

    # Validate priority
    valid_priorities = {"low", "normal", "urgent"}
    if body.priority not in valid_priorities:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Invalid priority. Must be one of: {valid_priorities}")

    # Check site is active
    site = db.scalars(select(Site).where(Site.id == body.site_id)).first()
    if not site:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Site not found")
    if not site.active:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Cannot create work order for inactive site")

    # Check due_by not in the past vs created_at (now)
    now = datetime.now(timezone.utc)
    if body.due_by and body.due_by < now:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="due_by cannot be in the past")

    warnings: list[str] = []
    if body.priority == "urgent" and not body.due_by:
        warnings.append("urgent orders suggest due_by within 24h")

    wo = WorkOrder(
        title=body.title,
        description=body.description,
        category=body.category,
        priority=body.priority,
        status="submitted",
        requester_id=current_user.user_id,
        site_id=body.site_id,
        location_id=body.location_id,
        due_by=body.due_by,
        created_at=now,
        updated_at=now,
    )
    db.add(wo)
    db.commit()
    db.refresh(wo)
    return _wo_to_out(wo, warnings=warnings if warnings else None)


@router.get("", response_model=WorkOrderListPage)
def list_work_orders(
    db: DbSession,
    current_user: AuthUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
    site_id: str | None = Query(default=None),
) -> WorkOrderListPage:
    stmt = select(WorkOrder)

    # Role scoping
    if current_user.role == "requester":
        stmt = stmt.where(WorkOrder.requester_id == current_user.user_id)
    elif current_user.role == "technician":
        stmt = stmt.where(WorkOrder.assignee_id == current_user.user_id)
    # admin and leadership see all

    if status_filter:
        stmt = stmt.where(WorkOrder.status == status_filter)
    if site_id:
        stmt = stmt.where(WorkOrder.site_id == site_id)

    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.scalar(count_stmt) or 0

    # Paginate
    offset = (page - 1) * page_size
    stmt = stmt.order_by(WorkOrder.created_at.desc()).offset(offset).limit(page_size)
    rows = list(db.scalars(stmt).all())

    items = [_wo_to_out(wo) for wo in rows]
    return WorkOrderListPage(items=items, total=total, page=page, page_size=page_size)


@router.get("/{work_order_id}", response_model=WorkOrderOut)
def get_work_order(work_order_id: str, db: DbSession, current_user: AuthUser) -> WorkOrderOut:
    wo = db.scalars(select(WorkOrder).where(WorkOrder.id == work_order_id)).first()
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
    _check_read_access(wo, current_user)
    return _wo_to_out(wo)


@router.patch("/{work_order_id}/status", response_model=WorkOrderOut)
def update_status(
    work_order_id: str,
    body: StatusUpdateRequest,
    db: DbSession,
    current_user: AuthUser,
) -> WorkOrderOut:
    wo = db.scalars(select(WorkOrder).where(WorkOrder.id == work_order_id)).first()
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")

    now = datetime.now(timezone.utc)
    new_status = body.status

    # Force close (admin only)
    if body.force_close:
        if current_user.role != "facilities_admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admin can force-close")
        new_status = "closed"
    else:
        # Check valid transition
        allowed = ALLOWED_TRANSITIONS.get(wo.status, set())
        if new_status not in allowed:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid transition from '{wo.status}' to '{new_status}'",
            )

        # Role guards for specific transitions
        if wo.status == "closed" and new_status == "in_progress":
            # Reopen requires reason
            if not body.reason:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Reopen requires a reason",
                )

        if current_user.role == "technician":
            # Tech can only move assigned->in_progress->completed on their own orders
            if wo.assignee_id != current_user.user_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Technicians can only update their own assigned orders")
            if new_status not in ("in_progress", "completed"):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Technicians can only move to in_progress or completed")

        if current_user.role == "requester":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requesters cannot change work order status")

        if current_user.role == "leadership":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Leadership cannot change work order status")

    # Record history
    history = WorkOrderStatusHistory(
        work_order_id=wo.id,
        from_status=wo.status,
        to_status=new_status,
        changed_by_user_id=current_user.user_id,
        changed_at=now,
        reason=body.reason,
    )
    db.add(history)

    # Apply transition
    old_status = wo.status
    wo.status = new_status
    wo.updated_at = now

    if new_status == "assigned" and wo.assigned_at is None:
        wo.assigned_at = now
    if new_status == "in_progress":
        wo.started_at = now
        if old_status == "closed":
            wo.reopen_reason = body.reason
    if new_status == "completed":
        wo.completed_at = now
    if new_status == "closed":
        wo.closed_at = now

    db.commit()
    db.refresh(wo)
    return _wo_to_out(wo)


@router.patch("/{work_order_id}/assign", response_model=WorkOrderOut)
def assign_work_order(
    work_order_id: str,
    body: AssignRequest,
    db: DbSession,
    current_user: AdminUser,
) -> WorkOrderOut:
    wo = db.scalars(select(WorkOrder).where(WorkOrder.id == work_order_id)).first()
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")

    # Verify assignee is a technician
    assignee = db.scalars(select(User).where(User.id == body.assignee_id)).first()
    if not assignee or assignee.role != "technician":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Assignee must be a technician")

    now = datetime.now(timezone.utc)

    # Record history (triaged -> assigned)
    history = WorkOrderStatusHistory(
        work_order_id=wo.id,
        from_status=wo.status,
        to_status="assigned",
        changed_by_user_id=current_user.user_id,
        changed_at=now,
    )
    db.add(history)

    wo.assignee_id = body.assignee_id
    wo.status = "assigned"
    wo.assigned_at = now
    wo.updated_at = now

    db.commit()
    db.refresh(wo)
    return _wo_to_out(wo)


def _check_read_access(wo: WorkOrder, user: AuthUser) -> None:
    """Raise 403 if user cannot read this work order."""
    if user.role in ("facilities_admin", "leadership"):
        return
    if user.role == "requester" and wo.requester_id == user.user_id:
        return
    if user.role == "technician" and wo.assignee_id == user.user_id:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
