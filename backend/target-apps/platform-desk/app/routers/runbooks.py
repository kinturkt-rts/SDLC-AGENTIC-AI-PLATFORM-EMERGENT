"""Runbook lifecycle management + Step CRUD."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.dependencies import DbSession, EditorRole, ViewerRole
from app.models.runbook import Runbook
from app.models.runbook_step import RunbookStep
from schemas.runbooks import (
    ActivationResponse,
    RunbookCreate,
    RunbookListPage,
    RunbookOut,
    SimilarRunbook,
)
from schemas.steps import StepCreate, StepOut, StepUpdate

router = APIRouter(tags=["runbooks"])


# ── Runbook CRUD ──────────────────────────────────────────────────────────────


@router.get("/api/v1/runbooks", response_model=RunbookListPage)
def list_runbooks(
    db: DbSession,
    _role: ViewerRole,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service_id: str | None = Query(default=None),
    lifecycle_status: str | None = Query(default=None),
):
    q = select(Runbook)
    count_q = select(func.count(Runbook.id))
    if service_id:
        q = q.where(Runbook.service_id == service_id)
        count_q = count_q.where(Runbook.service_id == service_id)
    if lifecycle_status:
        q = q.where(Runbook.lifecycle_status == lifecycle_status)
        count_q = count_q.where(Runbook.lifecycle_status == lifecycle_status)
    total = db.scalar(count_q) or 0
    rows = db.scalars(q.offset(offset).limit(limit)).all()
    return RunbookListPage(items=rows, total=total, limit=limit, offset=offset)


@router.get("/api/v1/runbooks/{id}", response_model=RunbookOut)
def get_runbook(id: str, db: DbSession, _role: ViewerRole):
    rb = db.get(Runbook, id)
    if not rb:
        raise HTTPException(status_code=404, detail="Runbook not found")
    return rb


@router.post("/api/v1/runbooks", response_model=RunbookOut, status_code=status.HTTP_201_CREATED)
def create_runbook(body: RunbookCreate, db: DbSession, _role: EditorRole):
    rb = Runbook(
        title=body.title,
        service_id=body.service_id,
        default_severity=body.default_severity,
        short_summary=body.short_summary,
        author=body.author,
        lifecycle_status="draft",
    )
    db.add(rb)
    db.commit()
    db.refresh(rb)
    return rb


@router.post("/api/v1/runbooks/{id}/activate", response_model=ActivationResponse)
def activate_runbook(id: str, db: DbSession, _role: EditorRole):
    rb = db.get(Runbook, id)
    if not rb:
        raise HTTPException(status_code=404, detail="Runbook not found")
    if rb.lifecycle_status != "draft":
        raise HTTPException(status_code=422, detail="Only draft runbooks can be activated")
    # Check at least one step
    step_count = db.scalar(
        select(func.count(RunbookStep.id)).where(RunbookStep.runbook_id == id)
    ) or 0
    if step_count == 0:
        raise HTTPException(status_code=422, detail="Runbook must have at least one step")
    # Check unique active title constraint
    existing = db.scalar(
        select(Runbook.id).where(
            Runbook.title == rb.title,
            Runbook.service_id == rb.service_id,
            Runbook.lifecycle_status == "active",
            Runbook.id != id,
        )
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail="An active runbook with the same title already exists for this service",
        )
    # Similar runbooks (advisory)
    similar: list[SimilarRunbook] = []
    active_runbooks = db.scalars(
        select(Runbook).where(
            Runbook.lifecycle_status == "active",
            Runbook.id != id,
        ).limit(50)
    ).all()
    title_lower = rb.title.lower()
    for arb in active_runbooks:
        arb_words = set(arb.title.lower().split())
        rb_words = set(title_lower.split())
        if not arb_words or not rb_words:
            continue
        overlap = len(arb_words & rb_words) / max(len(arb_words | rb_words), 1)
        if overlap > 0.3:
            similar.append(SimilarRunbook(
                runbook_id=str(arb.id), title=arb.title, score=round(overlap, 2)
            ))
    similar = sorted(similar, key=lambda x: x.score, reverse=True)[:5]

    rb.lifecycle_status = "active"
    db.commit()
    db.refresh(rb)

    # Index steps in vector store
    try:
        from app.services.vector_store import index_runbook_steps
        index_runbook_steps(db, id)
    except Exception:
        pass

    return ActivationResponse(status="activated", similar_runbooks=similar)


@router.post("/api/v1/runbooks/{id}/retire", response_model=RunbookOut)
def retire_runbook(id: str, db: DbSession, _role: EditorRole):
    rb = db.get(Runbook, id)
    if not rb:
        raise HTTPException(status_code=404, detail="Runbook not found")
    if rb.lifecycle_status != "active":
        raise HTTPException(status_code=422, detail="Only active runbooks can be retired")

    # Remove from vector index
    try:
        from app.services.vector_store import remove_runbook_steps
        remove_runbook_steps(id)
    except Exception:
        pass

    rb.lifecycle_status = "retired"
    db.commit()
    db.refresh(rb)
    return rb


# ── Step CRUD ─────────────────────────────────────────────────────────────────


def _get_runbook_or_404(runbook_id: str, db) -> Runbook:
    rb = db.get(Runbook, runbook_id)
    if not rb:
        raise HTTPException(status_code=404, detail="Runbook not found")
    return rb


@router.get("/api/v1/runbooks/{id}/steps", response_model=list[StepOut])
def list_steps(id: str, db: DbSession, _role: ViewerRole):
    _get_runbook_or_404(id, db)
    rows = db.scalars(
        select(RunbookStep)
        .where(RunbookStep.runbook_id == id)
        .order_by(RunbookStep.step_number)
    ).all()
    return rows


@router.post("/api/v1/runbooks/{id}/steps", response_model=StepOut, status_code=status.HTTP_201_CREATED)
def create_step(id: str, body: StepCreate, db: DbSession, _role: EditorRole):
    _get_runbook_or_404(id, db)
    step = RunbookStep(
        runbook_id=id,
        step_number=body.step_number,
        title=body.title,
        body_text=body.body_text,
        estimated_minutes=body.estimated_minutes,
        warning_callout=body.warning_callout,
    )
    db.add(step)
    db.commit()
    db.refresh(step)

    try:
        from app.services.vector_store import upsert_step
        rb = db.get(Runbook, id)
        if rb and rb.lifecycle_status == "active":
            upsert_step(step, id, rb.service_id)
    except Exception:
        pass

    return step


@router.get("/api/v1/runbooks/{id}/steps/{step_id}", response_model=StepOut)
def get_step(id: str, step_id: str, db: DbSession, _role: ViewerRole):
    _get_runbook_or_404(id, db)
    step = db.scalar(
        select(RunbookStep).where(
            RunbookStep.id == step_id,
            RunbookStep.runbook_id == id,
        )
    )
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")
    return step


@router.put("/api/v1/runbooks/{id}/steps/{step_id}", response_model=StepOut)
def update_step(id: str, step_id: str, body: StepUpdate, db: DbSession, _role: EditorRole):
    _get_runbook_or_404(id, db)
    step = db.scalar(
        select(RunbookStep).where(
            RunbookStep.id == step_id,
            RunbookStep.runbook_id == id,
        )
    )
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")
    updates = body.model_dump(exclude_unset=True)
    for k, v in updates.items():
        setattr(step, k, v)
    db.commit()
    db.refresh(step)

    try:
        from app.services.vector_store import upsert_step
        rb = db.get(Runbook, id)
        if rb and rb.lifecycle_status == "active":
            upsert_step(step, id, rb.service_id)
    except Exception:
        pass

    return step


@router.delete("/api/v1/runbooks/{id}/steps/{step_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_step(id: str, step_id: str, db: DbSession, _role: EditorRole):
    _get_runbook_or_404(id, db)
    step = db.scalar(
        select(RunbookStep).where(
            RunbookStep.id == step_id,
            RunbookStep.runbook_id == id,
        )
    )
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")
    db.delete(step)
    db.commit()
    return None
