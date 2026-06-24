"""Floor lead week management router."""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.dependencies import AuthUser, DbSession
from app.models.floor_lead_week import FloorLeadWeek
from app.models.user import User
from schemas.floor_lead import FloorLeadWeekCreate, FloorLeadWeekOut

router = APIRouter()


@router.get("/floor-leads", response_model=list[FloorLeadWeekOut])
def list_floor_leads(
    db: DbSession,
    current_user: AuthUser,
) -> list[FloorLeadWeekOut]:
    """List all floor-lead week assignments (admin)."""
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    rows = db.scalars(select(FloorLeadWeek)).all()
    return [FloorLeadWeekOut.model_validate(r) for r in rows]


@router.post("/floor-leads", response_model=FloorLeadWeekOut, status_code=status.HTTP_201_CREATED)
def create_floor_lead_assignment(
    body: FloorLeadWeekCreate,
    db: DbSession,
    current_user: AuthUser,
) -> FloorLeadWeekOut:
    """Assign a floor lead to a week (admin)."""
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")

    # Validate week_start is a Monday
    try:
        ws = date.fromisoformat(body.week_start)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid date format for week_start")

    if ws.weekday() != 0:
        raise HTTPException(status_code=422, detail="week_start must be a Monday")

    # Duplicate week check
    existing = db.scalars(
        select(FloorLeadWeek).where(FloorLeadWeek.week_start == ws)
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="A floor lead is already assigned for this week")

    # Validate user has floor_lead role
    user = db.scalars(
        select(User).where(User.id == body.floor_lead_user_id)
    ).first()
    if not user:
        raise HTTPException(status_code=422, detail="User not found")
    if user.role != "floor_lead":
        raise HTTPException(status_code=422, detail="Referenced user must have floor_lead role")

    assignment = FloorLeadWeek(
        id=str(uuid.uuid4()),
        week_start=ws,
        floor_lead_user_id=body.floor_lead_user_id,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return FloorLeadWeekOut.model_validate(assignment)
