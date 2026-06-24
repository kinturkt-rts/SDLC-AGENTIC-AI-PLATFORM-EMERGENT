"""Roster router — GET /roster, GET /roster/mine."""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.dependencies import AuthUser, DbSession
from app.models.shift_roster import ShiftRoster
from app.models.staff_profile import StaffProfile
from app.models.user import User
from schemas.roster import RosterRow

router = APIRouter()


def _build_roster_rows(rows: list) -> list[RosterRow]:
    """Convert query results to RosterRow list."""
    return [
        RosterRow(
            id=str(r.ShiftRoster.id),
            staff_id=str(r.ShiftRoster.staff_id),
            display_name=r.display_name,
            shift_date=r.ShiftRoster.shift_date.isoformat() if hasattr(r.ShiftRoster.shift_date, "isoformat") else str(r.ShiftRoster.shift_date),
            shift_window=r.ShiftRoster.shift_window,
        )
        for r in rows
    ]


@router.get("/roster", response_model=list[RosterRow])
def list_roster(
    db: DbSession,
    current_user: AuthUser,
    from_date: Optional[str] = Query(default=None, alias="from"),
    to_date: Optional[str] = Query(default=None, alias="to"),
) -> list[RosterRow]:
    """List all roster rows optionally filtered by date range."""
    stmt = (
        select(ShiftRoster, User.display_name)
        .join(StaffProfile, ShiftRoster.staff_id == StaffProfile.id)
        .join(User, StaffProfile.user_id == User.id)
    )
    if from_date:
        stmt = stmt.where(ShiftRoster.shift_date >= date.fromisoformat(from_date))
    if to_date:
        stmt = stmt.where(ShiftRoster.shift_date <= date.fromisoformat(to_date))
    rows = db.execute(stmt).all()
    return _build_roster_rows(rows)


@router.get("/roster/mine", response_model=list[RosterRow])
def my_roster(
    db: DbSession,
    current_user: AuthUser,
) -> list[RosterRow]:
    """Return roster rows for the authenticated user."""
    stmt = (
        select(ShiftRoster, User.display_name)
        .join(StaffProfile, ShiftRoster.staff_id == StaffProfile.id)
        .join(User, StaffProfile.user_id == User.id)
        .where(User.id == current_user.user_id)
    )
    rows = db.execute(stmt).all()
    return _build_roster_rows(rows)
