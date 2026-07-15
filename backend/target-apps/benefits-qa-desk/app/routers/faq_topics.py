"""FAQ topics router."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import AuthUser, ContributorOrAdmin
from app.models.faq_topic import FaqTopic
from schemas.faq_topics import FaqTopicCreate, FaqTopicOut

router = APIRouter()


@router.get("/api/v1/faq-topics", response_model=list[FaqTopicOut])
def list_faq_topics(
    current_user: AuthUser,
    db: Session = Depends(get_db),
) -> list[FaqTopicOut]:
    rows = db.scalars(select(FaqTopic).order_by(FaqTopic.label)).all()
    return [FaqTopicOut.model_validate(r) for r in rows]


@router.post("/api/v1/faq-topics", response_model=FaqTopicOut, status_code=201)
def create_faq_topic(
    body: FaqTopicCreate,
    current_user: ContributorOrAdmin,
    db: Session = Depends(get_db),
) -> FaqTopicOut:
    existing = db.scalars(select(FaqTopic).where(FaqTopic.label == body.label)).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="FAQ topic label already exists")
    topic = FaqTopic(
        label=body.label,
        created_by=current_user.user_id,
    )
    db.add(topic)
    db.commit()
    db.refresh(topic)
    return FaqTopicOut.model_validate(topic)
