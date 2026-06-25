"""Feedback router."""
from __future__ import annotations

import hashlib

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.dependencies import DbSession, AuthenticatedUser, AuthUser
from app.models.article import Article
from app.models.feedback import Feedback
from schemas.feedback import FeedbackCreate, FeedbackOut

router = APIRouter(tags=["feedback"])


@router.get("/api/v1/feedback", response_model=list[FeedbackOut])
def list_feedback(
    db: DbSession,
    current_user: AuthUser,
    limit: int = Query(default=20, ge=1, le=100),
) -> list[FeedbackOut]:
    """List feedback records."""
    stmt = select(Feedback).limit(limit)
    rows = db.scalars(stmt).all()
    return [FeedbackOut.model_validate(r) for r in rows]


@router.post("/api/v1/feedback", response_model=FeedbackOut, status_code=201)
def submit_feedback(
    body: FeedbackCreate,
    db: DbSession,
    current_user: AuthUser,
) -> FeedbackOut:
    if body.signal not in ("helpful", "not_helpful"):
        raise HTTPException(status_code=422, detail="Signal must be 'helpful' or 'not_helpful'")

    article = db.get(Article, body.article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    if article.state != "published":
        raise HTTPException(status_code=422, detail="Feedback only allowed on published articles")

    user_id_hash = hashlib.sha256(current_user.user_id.encode()).hexdigest()

    fb = Feedback(
        search_log_id=body.search_log_id,
        article_id=body.article_id,
        user_id_hash=user_id_hash,
        signal=body.signal,
    )
    db.add(fb)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Duplicate feedback")
    db.refresh(fb)
    return FeedbackOut.model_validate(fb)
