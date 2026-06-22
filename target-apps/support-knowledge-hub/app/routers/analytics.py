"""Analytics router — gaps dashboard."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.dependencies import DbSession, require_admin_or_leadership
from app.models.feedback import Feedback
from app.models.search_event import SearchEvent
from app.models.user import User
from schemas.analytics import GapItem, GapsResponse

router = APIRouter(tags=["analytics"])


@router.get("/gaps", response_model=GapsResponse)
def analytics_gaps(
    db: DbSession,
    current_user: User = Depends(require_admin_or_leadership),
    limit: int = Query(default=20, ge=1, le=100),
) -> GapsResponse:
    """Popular-gaps: queries with zero results or low helpful rate."""
    # Get all search events grouped by query_text
    from sqlalchemy import case, Integer, cast

    events = (
        db.query(
            SearchEvent.query_text,
            func.count(SearchEvent.id).label("count"),
        )
        .group_by(SearchEvent.query_text)
        .order_by(func.count(SearchEvent.id).desc())
        .limit(limit)
        .all()
    )

    gaps: list[GapItem] = []
    for row in events:
        query_text = row[0]
        count = row[1]

        # Calculate helpful rate for this query's results
        # Find search events with this query
        event_ids = (
            db.query(SearchEvent.id)
            .filter(SearchEvent.query_text == query_text)
            .all()
        )
        event_id_list = [e[0] for e in event_ids]

        if event_id_list:
            total_feedback = (
                db.query(Feedback)
                .filter(Feedback.search_event_id.in_(event_id_list))
                .count()
            )
            helpful_feedback = (
                db.query(Feedback)
                .filter(
                    Feedback.search_event_id.in_(event_id_list),
                    Feedback.rating == "helpful",
                )
                .count()
            )
            helpful_rate = helpful_feedback / total_feedback if total_feedback > 0 else 0.0
        else:
            helpful_rate = 0.0

        gaps.append(GapItem(
            query_text=query_text,
            count=count,
            helpful_rate=round(helpful_rate, 2),
        ))

    return GapsResponse(gaps=gaps)
