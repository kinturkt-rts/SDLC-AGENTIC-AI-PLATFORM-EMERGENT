"""Swap request router — full lifecycle endpoints."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import or_, select

from app.dependencies import AuthUser, DbSession
from app.models.floor_lead_week import FloorLeadWeek
from app.models.shift_roster import ShiftRoster
from app.models.staff_profile import StaffProfile
from app.models.swap_audit_log import SwapAuditLog
from app.models.swap_request import SwapRequest
from schemas.swap import AuditRow, SwapCreate, SwapDecision, SwapOut

router = APIRouter()


# ---- helpers ----

def _get_staff_profile_for_user(db, user_id: str) -> StaffProfile | None:
    return db.scalars(
        select(StaffProfile).where(StaffProfile.user_id == user_id)
    ).first()


def _add_audit(db, swap_request_id: str, action: str, actor_user_id: str, detail: dict | None = None) -> None:
    db.add(SwapAuditLog(
        id=str(uuid.uuid4()),
        swap_request_id=swap_request_id,
        action=action,
        actor_user_id=actor_user_id,
        detail=detail,
    ))


def _get_week_start(d: date) -> date:
    """Return the Monday of the ISO week containing date d."""
    return d - timedelta(days=d.weekday())


def _is_week_lead(db, user_id: str, shift_date: date) -> bool:
    """Check if user_id is the floor lead for the ISO week of shift_date."""
    week_start = _get_week_start(shift_date)
    row = db.scalars(
        select(FloorLeadWeek).where(
            FloorLeadWeek.week_start == week_start,
            FloorLeadWeek.floor_lead_user_id == user_id,
        )
    ).first()
    return row is not None


def _check_overlap(db, staff_id: str, shift_date: date, shift_window: str, exclude_shift_id: str | None = None) -> bool:
    """Return True if staff already has a shift on that date + window."""
    stmt = select(ShiftRoster).where(
        ShiftRoster.staff_id == staff_id,
        ShiftRoster.shift_date == shift_date,
        ShiftRoster.shift_window == shift_window,
    )
    if exclude_shift_id:
        stmt = stmt.where(ShiftRoster.id != exclude_shift_id)
    existing = db.scalars(stmt).first()
    return existing is not None


# ---- routes ----

@router.get("/swaps", response_model=list[SwapOut])
def list_swaps(
    db: DbSession,
    current_user: AuthUser,
    status_filter: str | None = Query(default=None, alias="status"),
    week_start: str | None = Query(default=None),
) -> list[SwapOut]:
    """List swap requests visible to current user."""
    stmt = select(SwapRequest)

    if status_filter:
        stmt = stmt.where(SwapRequest.status == status_filter)

    if week_start:
        ws = date.fromisoformat(week_start)
        we = ws + timedelta(days=6)
        stmt = stmt.join(ShiftRoster, SwapRequest.offered_shift_id == ShiftRoster.id)
        stmt = stmt.where(ShiftRoster.shift_date >= ws, ShiftRoster.shift_date <= we)

    # For staff: their own + open
    if current_user.role == "staff":
        stmt = stmt.where(
            or_(
                SwapRequest.offered_by_user_id == current_user.user_id,
                SwapRequest.claimed_by_user_id == current_user.user_id,
                SwapRequest.status == "open",
            )
        )

    rows = db.scalars(stmt).all()
    return [SwapOut.model_validate(r) for r in rows]


@router.post("/swaps", response_model=SwapOut, status_code=status.HTTP_201_CREATED)
def create_swap(
    body: SwapCreate,
    db: DbSession,
    current_user: AuthUser,
) -> SwapOut:
    """Create a swap offer (staff only)."""
    if current_user.role not in ("staff", "floor_lead"):
        raise HTTPException(status_code=403, detail="Only staff can create swap offers")

    shift = db.scalars(
        select(ShiftRoster).where(ShiftRoster.id == body.offered_shift_id)
    ).first()
    if not shift:
        raise HTTPException(status_code=422, detail="Shift not found")

    # Verify ownership
    profile = _get_staff_profile_for_user(db, current_user.user_id)
    if not profile or shift.staff_id != profile.id:
        raise HTTPException(status_code=403, detail="Shift does not belong to you")

    # Check shift date is not in the past
    today = date.today()
    shift_date_val = shift.shift_date if isinstance(shift.shift_date, date) else date.fromisoformat(str(shift.shift_date))
    if shift_date_val < today:
        raise HTTPException(status_code=422, detail="Cannot offer a shift in the past")

    # Check no active swap exists for this shift
    existing = db.scalars(
        select(SwapRequest).where(
            SwapRequest.offered_shift_id == body.offered_shift_id,
            SwapRequest.status.in_(["open", "claimed"]),
        )
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="An active swap already exists for this shift")

    swap_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    swap = SwapRequest(
        id=swap_id,
        offered_shift_id=body.offered_shift_id,
        offered_by_user_id=current_user.user_id,
        status="open",
        created_at=now,
        updated_at=now,
    )
    db.add(swap)
    _add_audit(db, swap_id, "created", current_user.user_id)
    db.commit()
    db.refresh(swap)
    return SwapOut.model_validate(swap)


@router.post("/swaps/{id}/claim", response_model=SwapOut)
def claim_swap(
    id: str,
    db: DbSession,
    current_user: AuthUser,
) -> SwapOut:
    """Claim an open swap (staff only)."""
    if current_user.role not in ("staff", "floor_lead"):
        raise HTTPException(status_code=403, detail="Only staff can claim swaps")

    swap = db.scalars(select(SwapRequest).where(SwapRequest.id == id)).first()
    if not swap:
        raise HTTPException(status_code=404, detail="Swap request not found")

    if swap.status != "open":
        raise HTTPException(status_code=409, detail="Swap is not open for claiming")

    if swap.offered_by_user_id == current_user.user_id:
        raise HTTPException(status_code=403, detail="Cannot claim your own swap")

    # Overlap check for claimer
    claimer_profile = _get_staff_profile_for_user(db, current_user.user_id)
    if not claimer_profile:
        raise HTTPException(status_code=422, detail="Claimer has no staff profile")

    shift = db.scalars(select(ShiftRoster).where(ShiftRoster.id == swap.offered_shift_id)).first()
    if not shift:
        raise HTTPException(status_code=422, detail="Offered shift no longer exists")

    shift_date_val = shift.shift_date if isinstance(shift.shift_date, date) else date.fromisoformat(str(shift.shift_date))
    if _check_overlap(db, claimer_profile.id, shift_date_val, shift.shift_window):
        raise HTTPException(status_code=422, detail="You already have a shift on the same date and window")

    now = datetime.now(timezone.utc)
    swap.status = "claimed"
    swap.claimed_by_user_id = current_user.user_id
    swap.claimed_at = now
    swap.updated_at = now
    _add_audit(db, id, "claimed", current_user.user_id)
    db.commit()
    db.refresh(swap)
    return SwapOut.model_validate(swap)


@router.post("/swaps/{id}/approve", response_model=SwapOut)
def approve_swap(
    id: str,
    body: SwapDecision,
    db: DbSession,
    current_user: AuthUser,
) -> SwapOut:
    """Approve a claimed swap (floor_lead for that week).

    Atomic operation: reassign the shift_roster row from offerer to accepter,
    update swap status, and append audit rows — all within one transaction.
    """
    if current_user.role not in ("floor_lead", "admin"):
        raise HTTPException(status_code=403, detail="Only floor leads can approve swaps")

    swap = db.scalars(select(SwapRequest).where(SwapRequest.id == id)).first()
    if not swap:
        raise HTTPException(status_code=404, detail="Swap request not found")

    if swap.status != "claimed":
        raise HTTPException(status_code=409, detail="Swap must be in claimed status to approve")

    shift = db.scalars(select(ShiftRoster).where(ShiftRoster.id == swap.offered_shift_id)).first()
    if not shift:
        raise HTTPException(status_code=422, detail="Offered shift no longer exists")

    shift_date_val = shift.shift_date if isinstance(shift.shift_date, date) else date.fromisoformat(str(shift.shift_date))

    # Week-guard: only the assigned floor lead for that week can approve
    if current_user.role == "floor_lead" and not _is_week_lead(db, current_user.user_id, shift_date_val):
        raise HTTPException(status_code=403, detail="You are not the floor lead for this shift's week")

    # Cannot approve own swap
    if swap.offered_by_user_id == current_user.user_id:
        raise HTTPException(status_code=403, detail="Cannot approve your own swap offer")

    # Re-validate overlap for accepter at approve time
    claimer_profile = _get_staff_profile_for_user(db, swap.claimed_by_user_id)
    if not claimer_profile:
        raise HTTPException(status_code=422, detail="Claimer no longer has a staff profile")

    # Exclude the current shift being transferred when checking overlap
    if _check_overlap(db, claimer_profile.id, shift_date_val, shift.shift_window, exclude_shift_id=str(shift.id)):
        raise HTTPException(status_code=422, detail="Accepter now has a conflicting shift on that date/window")

    # Atomic roster update: reassign the shift from offerer to accepter
    now = datetime.now(timezone.utc)
    old_staff_id = str(shift.staff_id)

    # Transfer the shift to the claimer (keeps FK intact)
    shift.staff_id = claimer_profile.id
    shift.created_at = now  # update timestamp to reflect reassignment

    swap.status = "approved"
    swap.decided_by_user_id = current_user.user_id
    swap.decided_at = now
    swap.decision_note = body.decision_note
    swap.updated_at = now

    _add_audit(db, id, "approved", current_user.user_id, {"from_status": "claimed", "to_status": "approved"})
    _add_audit(db, id, "roster_updated", current_user.user_id, {
        "removed_staff_id": old_staff_id,
        "added_staff_id": str(claimer_profile.id),
    })

    db.commit()
    db.refresh(swap)
    return SwapOut.model_validate(swap)


@router.post("/swaps/{id}/deny", response_model=SwapOut)
def deny_swap(
    id: str,
    body: SwapDecision,
    db: DbSession,
    current_user: AuthUser,
) -> SwapOut:
    """Deny a claimed swap (floor_lead for that week)."""
    if current_user.role not in ("floor_lead", "admin"):
        raise HTTPException(status_code=403, detail="Only floor leads can deny swaps")

    swap = db.scalars(select(SwapRequest).where(SwapRequest.id == id)).first()
    if not swap:
        raise HTTPException(status_code=404, detail="Swap request not found")

    if swap.status != "claimed":
        raise HTTPException(status_code=409, detail="Swap must be in claimed status to deny")

    shift = db.scalars(select(ShiftRoster).where(ShiftRoster.id == swap.offered_shift_id)).first()
    if not shift:
        raise HTTPException(status_code=422, detail="Offered shift no longer exists")

    shift_date_val = shift.shift_date if isinstance(shift.shift_date, date) else date.fromisoformat(str(shift.shift_date))

    # Week-guard
    if current_user.role == "floor_lead" and not _is_week_lead(db, current_user.user_id, shift_date_val):
        raise HTTPException(status_code=403, detail="You are not the floor lead for this shift's week")

    now = datetime.now(timezone.utc)
    swap.status = "denied"
    swap.decided_by_user_id = current_user.user_id
    swap.decided_at = now
    swap.decision_note = body.decision_note
    swap.updated_at = now

    _add_audit(db, id, "denied", current_user.user_id, {"from_status": "claimed", "to_status": "denied"})
    db.commit()
    db.refresh(swap)
    return SwapOut.model_validate(swap)


@router.post("/swaps/{id}/cancel", response_model=SwapOut)
def cancel_swap(
    id: str,
    db: DbSession,
    current_user: AuthUser,
) -> SwapOut:
    """Cancel a swap offer (offerer only)."""
    swap = db.scalars(select(SwapRequest).where(SwapRequest.id == id)).first()
    if not swap:
        raise HTTPException(status_code=404, detail="Swap request not found")

    if swap.offered_by_user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Only the offerer can cancel this swap")

    if swap.status in ("approved", "denied", "cancelled"):
        raise HTTPException(status_code=409, detail="Swap is already in a terminal state")

    now = datetime.now(timezone.utc)
    prev_status = swap.status
    swap.status = "cancelled"
    swap.updated_at = now

    _add_audit(db, id, "cancelled", current_user.user_id, {"from_status": prev_status, "to_status": "cancelled"})
    db.commit()
    db.refresh(swap)
    return SwapOut.model_validate(swap)


@router.get("/swaps/{id}/audit", response_model=list[AuditRow])
def swap_audit(
    id: str,
    db: DbSession,
    current_user: AuthUser,
) -> list[AuditRow]:
    """Get audit log for a specific swap (admin or floor_lead)."""
    if current_user.role not in ("floor_lead", "admin"):
        raise HTTPException(status_code=403, detail="Forbidden")

    rows = db.scalars(
        select(SwapAuditLog)
        .where(SwapAuditLog.swap_request_id == id)
        .order_by(SwapAuditLog.created_at)
    ).all()
    return [AuditRow.model_validate(r) for r in rows]
