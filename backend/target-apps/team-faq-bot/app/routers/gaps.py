"""GET /api/v1/gaps — gap analysis list of unanswered questions."""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.dependencies import DbSession, require_admin_api_key
from app.models.question_log import QuestionLog
from schemas.gaps import GapItem

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/gaps", response_model=list[GapItem])
def list_gaps(
    db: DbSession,
    _key: str = Depends(require_admin_api_key),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
) -> list[GapItem]:
    """Return questions that received 'not_in_faq' status, optionally filtered by date."""
    stmt = (
        select(QuestionLog)
        .where(QuestionLog.status == "not_in_faq")
        .order_by(QuestionLog.logged_at.desc())
    )

    if from_date:
        from_dt = datetime(from_date.year, from_date.month, from_date.day, tzinfo=timezone.utc)
        stmt = stmt.where(QuestionLog.logged_at >= from_dt)

    if to_date:
        # Include the entire 'to' day
        to_dt = datetime(to_date.year, to_date.month, to_date.day, 23, 59, 59, tzinfo=timezone.utc)
        stmt = stmt.where(QuestionLog.logged_at <= to_dt)

    rows = db.scalars(stmt).all()
    return [
        GapItem(
            id=row.id,
            question_text=row.question_text,
            logged_at=row.logged_at.isoformat() if row.logged_at else "",
        )
        for row in rows
    ]
