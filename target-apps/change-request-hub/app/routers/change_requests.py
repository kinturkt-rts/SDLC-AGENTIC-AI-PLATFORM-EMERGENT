"""Change requests router — lifecycle management."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.dependencies import AuthUser, DbSession, ManagerUser
from app.models.approval_record import ApprovalRecord
from app.models.blackout_window import BlackoutWindow
from app.models.change_request import ChangeRequest
from app.models.environment import Environment
from app.models.service import Service
from app.models.status_history import StatusHistory
from app.models.user import User
from schemas.change_request import (
    AssignRequest,
    ChangeRequestCreate,
    ChangeRequestDetail,
    ChangeRequestListPage,
    ChangeRequestOut,
    StatusTransition,
)

router = APIRouter()

# Valid status transitions: from -> set of allowed to
_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"submitted"},
    "submitted": {"approved", "rejected"},
    "approved": {"scheduled", "implementing"},  # implementing only for emergency
    "scheduled": {"implementing"},
    "implementing": {"completed"},
    "completed": {"closed"},
}


@router.get("/api/v1/change-requests", response_model=ChangeRequestListPage)
def list_change_requests(
    db: DbSession,
    current_user: AuthUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
) -> ChangeRequestListPage:
    """Role-scoped paginated list."""
    stmt = select(ChangeRequest)
    count_stmt = select(func.count(ChangeRequest.id))

    # Role scoping
    if current_user.role == "requester":
        stmt = stmt.where(ChangeRequest.requester_id == current_user.user_id)
        count_stmt = count_stmt.where(ChangeRequest.requester_id == current_user.user_id)
    elif current_user.role == "implementer":
        stmt = stmt.where(ChangeRequest.implementer_id == current_user.user_id)
        count_stmt = count_stmt.where(ChangeRequest.implementer_id == current_user.user_id)
    # manager + leadership see all

    if status_filter:
        stmt = stmt.where(ChangeRequest.status == status_filter)
        count_stmt = count_stmt.where(ChangeRequest.status == status_filter)

    total = db.scalar(count_stmt) or 0
    rows = db.scalars(
        stmt.order_by(ChangeRequest.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return ChangeRequestListPage(items=rows, total=total, page=page, page_size=page_size)


@router.post("/api/v1/change-requests", response_model=ChangeRequestOut, status_code=status.HTTP_201_CREATED)
def create_change_request(
    body: ChangeRequestCreate,
    db: DbSession,
    current_user: AuthUser,
) -> ChangeRequestOut:
    """Create a new change request (requester or manager)."""
    if current_user.role not in ("requester", "manager"):
        raise HTTPException(status_code=403, detail="Only requesters and managers can create change requests")

    # Validate service
    svc = db.scalars(select(Service).where(Service.id == body.service_id)).first()
    if not svc:
        raise HTTPException(status_code=422, detail="Service not found")
    if not svc.active:
        raise HTTPException(status_code=422, detail="Service is inactive")

    # Validate environment
    env = db.scalars(select(Environment).where(Environment.id == body.target_environment_id)).first()
    if not env:
        raise HTTPException(status_code=422, detail="Environment not found")
    if not env.active:
        raise HTTPException(status_code=422, detail="Environment is inactive")

    # Validate change_type and risk
    if body.change_type not in ("standard", "normal", "emergency"):
        raise HTTPException(status_code=422, detail="Invalid change_type")
    if body.risk not in ("low", "medium", "high", "critical"):
        raise HTTPException(status_code=422, detail="Invalid risk value")

    cr = ChangeRequest(
        title=body.title,
        description=body.description,
        service_id=body.service_id,
        target_environment_id=body.target_environment_id,
        change_type=body.change_type,
        risk=body.risk,
        status="draft",
        requester_id=current_user.user_id,
        planned_start=body.planned_start,
        planned_end=body.planned_end,
        rollback_plan=body.rollback_plan,
    )
    db.add(cr)
    db.commit()
    db.refresh(cr)
    return cr  # type: ignore[return-value]


@router.get("/api/v1/change-requests/{id}", response_model=ChangeRequestDetail)
def get_change_request(
    id: str,
    db: DbSession,
    current_user: AuthUser,
) -> ChangeRequestDetail:
    """Get change request detail with approval_records and status_history."""
    cr = db.scalars(select(ChangeRequest).where(ChangeRequest.id == id)).first()
    if not cr:
        raise HTTPException(status_code=404, detail="Change request not found")
    return cr  # type: ignore[return-value]


@router.patch("/api/v1/change-requests/{id}/status", response_model=ChangeRequestOut)
def transition_status(
    id: str,
    body: StatusTransition,
    db: DbSession,
    current_user: AuthUser,
) -> ChangeRequestOut:
    """Transition change request status per lifecycle rules."""
    cr = db.scalars(select(ChangeRequest).where(ChangeRequest.id == id)).first()
    if not cr:
        raise HTTPException(status_code=404, detail="Change request not found")

    from_status = cr.status
    to_status = body.to_status

    # Validate transition is allowed
    allowed = _TRANSITIONS.get(from_status, set())
    if to_status not in allowed:
        raise HTTPException(status_code=422, detail=f"Invalid transition from '{from_status}' to '{to_status}'")

    # Role checks per transition
    if from_status == "draft" and to_status == "submitted":
        if current_user.role not in ("requester", "manager"):
            raise HTTPException(status_code=403, detail="Only requester or manager can submit")
        if current_user.role == "requester" and cr.requester_id != current_user.user_id:
            raise HTTPException(status_code=403, detail="Requester can only submit own changes")

    elif from_status == "submitted" and to_status in ("approved", "rejected"):
        if current_user.role != "manager":
            raise HTTPException(status_code=403, detail="Only managers can approve/reject")
        if to_status == "rejected" and not body.reason:
            raise HTTPException(status_code=422, detail="Reason required for rejection")
        # Create approval record
        ar = ApprovalRecord(
            change_id=id,
            approver_id=current_user.user_id,
            decision=to_status,
            comment=body.reason,
            decided_at=datetime.now(timezone.utc),
        )
        db.add(ar)
        if to_status == "approved":
            cr.approved_at = datetime.now(timezone.utc)

    elif from_status == "approved" and to_status == "scheduled":
        if current_user.role != "manager":
            raise HTTPException(status_code=403, detail="Only managers can schedule")
        # Use provided planned_start/end or existing ones
        p_start = body.planned_start or cr.planned_start
        p_end = body.planned_end or cr.planned_end
        if body.planned_start:
            cr.planned_start = body.planned_start
        if body.planned_end:
            cr.planned_end = body.planned_end
        # Blackout overlap check
        overlap = db.scalars(
            select(BlackoutWindow).where(
                BlackoutWindow.environment_id == cr.target_environment_id,
                BlackoutWindow.start_at < p_end,
                BlackoutWindow.end_at > p_start,
            )
        ).first()
        if overlap:
            raise HTTPException(
                status_code=422,
                detail=f"Conflicts with blackout window {overlap.id}: {overlap.reason}",
            )
        cr.scheduled_at = datetime.now(timezone.utc)

    elif from_status == "approved" and to_status == "implementing":
        # Emergency shortcut
        if cr.change_type != "emergency":
            raise HTTPException(status_code=422, detail="Only emergency changes can skip scheduled")
        if current_user.role not in ("manager", "implementer"):
            raise HTTPException(status_code=403, detail="Only managers or implementers can start emergency")
        cr.started_at = datetime.now(timezone.utc)

    elif from_status == "scheduled" and to_status == "implementing":
        if current_user.role != "implementer":
            raise HTTPException(status_code=403, detail="Only implementers can start implementing")
        if cr.implementer_id and cr.implementer_id != current_user.user_id:
            raise HTTPException(status_code=403, detail="Only the assigned implementer can start")
        cr.started_at = datetime.now(timezone.utc)

    elif from_status == "implementing" and to_status == "completed":
        if current_user.role != "implementer":
            raise HTTPException(status_code=403, detail="Only implementers can complete")
        if cr.implementer_id != current_user.user_id:
            raise HTTPException(status_code=403, detail="Only the assigned implementer can complete")
        cr.completed_at = datetime.now(timezone.utc)

    elif from_status == "completed" and to_status == "closed":
        if current_user.role != "manager":
            raise HTTPException(status_code=403, detail="Only managers can close")
        cr.closed_at = datetime.now(timezone.utc)

    # Record status change
    cr.status = to_status
    cr.updated_at = datetime.now(timezone.utc)
    if to_status == "submitted":
        cr.submitted_at = datetime.now(timezone.utc)

    history = StatusHistory(
        change_id=id,
        from_status=from_status,
        to_status=to_status,
        actor_id=current_user.user_id,
        changed_at=datetime.now(timezone.utc),
        reason=body.reason,
    )
    db.add(history)
    db.commit()
    db.refresh(cr)
    return cr  # type: ignore[return-value]


@router.patch("/api/v1/change-requests/{id}/assign", response_model=ChangeRequestOut)
def assign_implementer(
    id: str,
    body: AssignRequest,
    db: DbSession,
    current_user: ManagerUser,
) -> ChangeRequestOut:
    """Assign an implementer to a change request."""
    cr = db.scalars(select(ChangeRequest).where(ChangeRequest.id == id)).first()
    if not cr:
        raise HTTPException(status_code=404, detail="Change request not found")

    # Validate implementer exists and has implementer role
    impl = db.scalars(select(User).where(User.id == body.implementer_id)).first()
    if not impl:
        raise HTTPException(status_code=422, detail="User not found")
    if impl.role != "implementer":
        raise HTTPException(status_code=422, detail="User is not an implementer")

    cr.implementer_id = body.implementer_id
    cr.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(cr)
    return cr  # type: ignore[return-value]
