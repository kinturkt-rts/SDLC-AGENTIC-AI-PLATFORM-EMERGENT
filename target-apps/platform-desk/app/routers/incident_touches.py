"""Incident touch log — Viewer+."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.dependencies import DbSession, ViewerRole
from app.models.incident_touch import IncidentTouch
from app.models.runbook import Runbook
from schemas.incident_touches import IncidentTouchCreate, IncidentTouchOut

router = APIRouter(tags=["incident-touches"])


@router.get("/api/v1/incident-touches", response_model=list[IncidentTouchOut])
def list_incident_touches(
    db: DbSession,
    _role: ViewerRole,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    runbook_id: str | None = Query(default=None),
):
    """List incident touches, optionally filtered by runbook."""
    q = select(IncidentTouch).order_by(IncidentTouch.created_at.desc())
    if runbook_id:
        q = q.where(IncidentTouch.runbook_id == runbook_id)
    rows = db.scalars(q.offset(offset).limit(limit)).all()
    return rows


@router.post("/api/v1/incident-touches", response_model=IncidentTouchOut, status_code=status.HTTP_201_CREATED)
def create_incident_touch(body: IncidentTouchCreate, db: DbSession, role: ViewerRole):
    if not body.ticket_reference or not body.ticket_reference.strip():
        raise HTTPException(status_code=422, detail="ticket_reference is required")
    # Verify runbook exists
    rb = db.get(Runbook, body.runbook_id)
    if not rb:
        raise HTTPException(status_code=404, detail="Runbook not found")
    touch = IncidentTouch(
        runbook_id=body.runbook_id,
        step_number=body.step_number,
        ticket_reference=body.ticket_reference.strip(),
        notes=body.notes,
        role=role,
    )
    db.add(touch)
    db.commit()
    db.refresh(touch)
    return touch
