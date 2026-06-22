"""Feedback router."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.dependencies import CurrentUser, DbSession
from app.models.feedback import Feedback
from schemas.feedback import FeedbackCreate, FeedbackOut

router = APIRouter(tags=["feedback"])


@router.post("", response_model=FeedbackOut, status_code=201)
def create_feedback(
    body: FeedbackCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> Feedback:
    """Submit feedback for a search result. 409 on duplicate."""
    if body.rating not in ("helpful", "not_helpful"):
        raise HTTPException(status_code=422, detail="Rating must be 'helpful' or 'not_helpful'")

    existing = (
        db.query(Feedback)
        .filter(
            Feedback.search_event_id == body.search_event_id,
            Feedback.article_id == body.article_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Feedback already submitted for this article in this search session")

    now = datetime.now(timezone.utc)
    fb = Feedback(
        id=str(uuid.uuid4()),
        search_event_id=body.search_event_id,
        article_id=body.article_id,
        rating=body.rating,
        timestamp=now,
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)
    return fb
