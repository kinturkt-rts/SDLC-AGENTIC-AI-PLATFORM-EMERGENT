"""Bug report API routes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.config import get_settings
from app.dependencies import AdminKeyDep, ApiKeyDep, DbSession
from app.models.bug import Bug, BugStatus
from app.services.dedup_service import DedupService, get_dedup_service
from schemas.bug import (
    BugCreate,
    BugOut,
    BugSubmitResponse,
    BugUpdate,
    MarkDuplicateRequest,
    SimilarBugOut,
)

router = APIRouter()

DedupDep = Annotated[DedupService, Depends(get_dedup_service)]


def _bug_out(bug: Bug) -> BugOut:
    return BugOut.model_validate(bug)


def _build_submit_response(
    bug: Bug,
    similar: list,
) -> BugSubmitResponse:
    settings = get_settings()
    top_score = similar[0].score if similar else None
    likely = top_score is not None and top_score >= settings.dedup_threshold
    return BugSubmitResponse(
        bug=_bug_out(bug),
        similar_bugs=[
            SimilarBugOut(
                id=item.id,
                title=item.title,
                description=item.description,
                similarity_score=round(item.score, 4),
            )
            for item in similar
        ],
        likely_duplicate=likely,
        top_similarity_score=round(top_score, 4) if top_score is not None else None,
    )


def _create_bug_with_embedding(
    db: DbSession,
    dedup: DedupService,
    *,
    title: str,
    description: str,
) -> BugSubmitResponse:
    bug = Bug(
        id=str(uuid.uuid4()),
        title=title,
        description=description,
        status=BugStatus.OPEN,
    )
    db.add(bug)
    db.commit()
    db.refresh(bug)

    embedding = dedup.embed_description(description)
    dedup.store_embedding(db, bug.id, embedding)
    similar = dedup.find_similar(
        db, embedding=embedding, exclude_bug_id=bug.id
    )
    return _build_submit_response(bug, similar)


@router.post("/", response_model=BugSubmitResponse, status_code=201)
def create_bug(
    payload: BugCreate,
    db: DbSession,
    api_key: ApiKeyDep,
    dedup: DedupDep,
) -> BugSubmitResponse:
    return _create_bug_with_embedding(
        db, dedup, title=payload.title, description=payload.description
    )


@router.get("/", response_model=list[BugOut])
def list_bugs(
    db: DbSession,
    api_key: ApiKeyDep,
    status: BugStatus | None = None,
) -> list[BugOut]:
    query = db.query(Bug)
    if status is not None:
        query = query.filter(Bug.status == status)
    bugs = query.order_by(Bug.created_at.desc()).all()
    return [_bug_out(b) for b in bugs]


@router.get("/{bug_id}", response_model=BugOut)
def get_bug(bug_id: str, db: DbSession, api_key: ApiKeyDep) -> BugOut:
    bug = db.get(Bug, bug_id)
    if not bug:
        raise HTTPException(status_code=404, detail="Bug not found")
    return _bug_out(bug)


@router.patch("/{bug_id}", response_model=BugSubmitResponse)
def update_bug(
    bug_id: str,
    payload: BugUpdate,
    db: DbSession,
    api_key: ApiKeyDep,
    dedup: DedupDep,
) -> BugSubmitResponse:
    bug = db.get(Bug, bug_id)
    if not bug:
        raise HTTPException(status_code=404, detail="Bug not found")
    if bug.status != BugStatus.OPEN:
        raise HTTPException(status_code=400, detail="Only open bugs can be updated")

    description_changed = False
    if payload.title is not None:
        bug.title = payload.title
    if payload.description is not None:
        bug.description = payload.description
        description_changed = True
    bug.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(bug)

    if description_changed:
        embedding = dedup.embed_description(bug.description)
        dedup.store_embedding(db, bug.id, embedding)
        similar = dedup.find_similar(
            db, embedding=embedding, exclude_bug_id=bug.id
        )
        return _build_submit_response(bug, similar)

    return BugSubmitResponse(
        bug=_bug_out(bug),
        similar_bugs=[],
        likely_duplicate=False,
        top_similarity_score=None,
    )


@router.post("/{bug_id}/mark-duplicate", response_model=BugOut)
def mark_duplicate(
    bug_id: str,
    payload: MarkDuplicateRequest,
    db: DbSession,
    api_key: ApiKeyDep,
    admin_key: AdminKeyDep,
) -> BugOut:
    bug = db.get(Bug, bug_id)
    if not bug:
        raise HTTPException(status_code=404, detail="Bug not found")
    target = db.get(Bug, payload.duplicate_of_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target bug not found")
    if bug.id == target.id:
        raise HTTPException(status_code=400, detail="A bug cannot duplicate itself")
    if target.status != BugStatus.OPEN:
        raise HTTPException(status_code=400, detail="Target bug must be open")

    bug.status = BugStatus.DUPLICATE
    bug.duplicate_of_id = target.id
    bug.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(bug)
    return _bug_out(bug)


@router.post("/{bug_id}/close", response_model=BugOut)
def close_bug(
    bug_id: str,
    db: DbSession,
    api_key: ApiKeyDep,
    admin_key: AdminKeyDep,
) -> BugOut:
    bug = db.get(Bug, bug_id)
    if not bug:
        raise HTTPException(status_code=404, detail="Bug not found")
    if bug.status != BugStatus.OPEN:
        raise HTTPException(status_code=400, detail="Only open bugs can be closed")

    bug.status = BugStatus.CLOSED
    bug.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(bug)
    return _bug_out(bug)
