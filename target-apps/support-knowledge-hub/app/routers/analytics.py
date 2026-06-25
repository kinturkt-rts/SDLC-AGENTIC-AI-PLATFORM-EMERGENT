"""Analytics router."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func as sa_func, case

from app.dependencies import DbSession, AuthenticatedUser, require_role
from app.models.search_log import SearchLog
from schemas.analytics import GapItem

router = APIRouter(tags=["analytics"])


@router.get("/api/v1/analytics/gaps", response_model=list[GapItem])
def get_gaps(
    db: DbSession,
    current_user: AuthenticatedUser = Depends(require_role("knowledge_admin", "leadership")),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[GapItem]:
    """Return search queries that returned weak or no results."""
    stmt = (
        select(
            SearchLog.query_text,
            sa_func.count(SearchLog.id).label("search_count"),
            sa_func.sum(
                case(
                    (SearchLog.result_count == 0, 1),
                    else_=0,
                )
            ).label("weak_result_count"),
        )
        .group_by(SearchLog.query_text)
        .order_by(sa_func.count(SearchLog.id).desc())
        .limit(limit)
    )
    rows = db.execute(stmt).all()
    return [
        GapItem(
            query_text=row.query_text,
            search_count=row.search_count,
            weak_result_count=int(row.weak_result_count or 0),
        )
        for row in rows
    ]
