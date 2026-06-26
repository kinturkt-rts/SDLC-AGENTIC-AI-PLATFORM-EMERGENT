"""Bug CRUD and deduplication endpoints."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.dependencies import require_api_key, require_admin
from app.models.api_key import ApiKey
from app.models.bug import Bug
from app.models.pg_types import BugStatus
from app.services.bedrock_client import get_bedrock_client
from app.services.embedding_store import embedding_as_list, embedding_bind_value
from app.services.vector_search import find_similar_bugs
from schemas.bug import (
    BugCreate,
    BugCreateResponse,
    BugOut,
    BugUpdate,
    BugUpdateResponse,
    DuplicateRequest,
    SimilarBug,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["bugs"])


def _embed_description(description: str) -> list[float]:
    """Generate embedding for a bug description via Bedrock."""
    client = get_bedrock_client()
    return client.embed(description)


def _compute_dedup(
    db: Session,
    embedding: list[float],
    exclude_id: str | None = None,
) -> tuple[list[SimilarBug], bool, str | None]:
    """Run vector search and compute likely_duplicate flag."""
    settings = get_settings()
    similar_raw = find_similar_bugs(
        db,
        embedding,
        top_k=settings.top_k,
        exclude_id=exclude_id,
    )
    similar_bugs = [SimilarBug(**s) for s in similar_raw]
    likely_duplicate = False
    top_match_id: str | None = None
    if similar_bugs:
        top_score = similar_bugs[0].similarity_score
        if top_score >= settings.similarity_threshold:
            likely_duplicate = True
            top_match_id = similar_bugs[0].id
    return similar_bugs, likely_duplicate, top_match_id


@router.post("", response_model=BugCreateResponse, status_code=201)
def create_bug(
    body: BugCreate,
    db: Session = Depends(get_db),
    _auth: ApiKey = Depends(require_api_key),
) -> BugCreateResponse:
    """Create a bug with dedup check."""
    embedding = _embed_description(body.description)
    dialect = db.bind.dialect.name if db.bind else "sqlite"

    bug = Bug(
        id=str(uuid.uuid4()),
        title=body.title,
        description=body.description,
        embedding=embedding_bind_value(embedding, dialect=dialect),
        status=BugStatus.open.value,
    )
    db.add(bug)
    db.commit()
    db.refresh(bug)

    similar_bugs, likely_duplicate, top_match_id = _compute_dedup(db, embedding)

    return BugCreateResponse(
        bug=BugOut.model_validate(bug),
        similar_bugs=similar_bugs,
        likely_duplicate=likely_duplicate,
        top_match_id=top_match_id,
    )


@router.patch("/{bug_id}", response_model=BugUpdateResponse)
def update_bug(
    bug_id: str,
    body: BugUpdate,
    db: Session = Depends(get_db),
    _auth: ApiKey = Depends(require_api_key),
) -> BugUpdateResponse:
    """Update a bug; re-embed if description changes."""
    bug = db.scalars(select(Bug).where(Bug.id == bug_id)).first()
    if not bug:
        raise HTTPException(status_code=404, detail="Bug not found")

    updates = body.model_dump(exclude_unset=True)
    description_changed = "description" in updates and updates["description"] != bug.description

    for k, v in updates.items():
        setattr(bug, k, v)

    embedding: list[float] | None = None
    if description_changed:
        embedding = _embed_description(bug.description)
        dialect = db.bind.dialect.name if db.bind else "sqlite"
        bug.embedding = embedding_bind_value(embedding, dialect=dialect)

    bug.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(bug)

    if embedding is None:
        embedding = embedding_as_list(bug.embedding)

    similar_bugs: list[SimilarBug] = []
    likely_duplicate = False
    if embedding:
        similar_bugs, likely_duplicate, _ = _compute_dedup(db, embedding, exclude_id=bug_id)

    return BugUpdateResponse(
        bug=BugOut.model_validate(bug),
        similar_bugs=similar_bugs,
        likely_duplicate=likely_duplicate,
    )


@router.get("/{bug_id}", response_model=BugOut)
def get_bug(
    bug_id: str,
    db: Session = Depends(get_db),
    _auth: ApiKey = Depends(require_api_key),
) -> BugOut:
    """Retrieve a single bug by ID."""
    bug = db.scalars(select(Bug).where(Bug.id == bug_id)).first()
    if not bug:
        raise HTTPException(status_code=404, detail="Bug not found")
    return BugOut.model_validate(bug)


@router.post("/{bug_id}/duplicate", response_model=BugOut)
def mark_duplicate(
    bug_id: str,
    body: DuplicateRequest,
    db: Session = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
) -> BugOut:
    """Mark a bug as duplicate (admin only)."""
    bug = db.scalars(select(Bug).where(Bug.id == bug_id)).first()
    if not bug:
        raise HTTPException(status_code=404, detail="Bug not found")

    # Verify canonical bug exists
    canonical = db.scalars(
        select(Bug).where(Bug.id == body.canonical_bug_id)
    ).first()
    if not canonical:
        raise HTTPException(status_code=404, detail="Canonical bug not found")

    bug.status = BugStatus.duplicate.value
    bug.duplicate_of = body.canonical_bug_id
    bug.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(bug)
    return BugOut.model_validate(bug)


@router.post("/{bug_id}/resolve", response_model=BugOut)
def resolve_bug(
    bug_id: str,
    db: Session = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
) -> BugOut:
    """Resolve a bug (admin only)."""
    bug = db.scalars(select(Bug).where(Bug.id == bug_id)).first()
    if not bug:
        raise HTTPException(status_code=404, detail="Bug not found")

    bug.status = BugStatus.resolved.value
    bug.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(bug)
    return BugOut.model_validate(bug)
