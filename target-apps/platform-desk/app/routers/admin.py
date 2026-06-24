"""Admin analytics and index refresh."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.config import get_settings
from app.dependencies import AdminRole, DbSession
from app.models.incident_touch import IncidentTouch
from app.models.runbook import Runbook
from app.models.runbook_step import RunbookStep
from app.models.search_event import SearchEvent
from app.models.service import Service
from schemas.analytics import (
    AnalyticsResponse,
    IndexRefreshResponse,
    RelianceItem,
    ResponseTimeStats,
    TopQuery,
)

router = APIRouter(tags=["admin"])


@router.get("/api/v1/admin/report/reliance", response_model=list[RelianceItem])
def reliance_report(
    db: DbSession,
    _role: AdminRole,
    days: int = Query(default=30, ge=1, le=365),
):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        db.execute(
            select(
                Service.name.label("service_name"),
                func.count(IncidentTouch.id).label("touch_count"),
            )
            .join(Runbook, Runbook.id == IncidentTouch.runbook_id)
            .join(Service, Service.id == Runbook.service_id)
            .where(IncidentTouch.created_at >= cutoff)
            .group_by(Service.name)
            .order_by(func.count(IncidentTouch.id).desc())
        )
        .all()
    )
    return [RelianceItem(service_name=r.service_name, touch_count=r.touch_count) for r in rows]


@router.get("/api/v1/admin/analytics", response_model=AnalyticsResponse)
def search_analytics(
    db: DbSession,
    _role: AdminRole,
    top_n: int = Query(default=25, ge=1, le=100),
):
    settings = get_settings()
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    # Top queries by frequency
    top_q = (
        db.execute(
            select(
                SearchEvent.query_text,
                func.count(SearchEvent.id).label("cnt"),
            )
            .where(SearchEvent.created_at >= cutoff)
            .group_by(SearchEvent.query_text)
            .order_by(func.count(SearchEvent.id).desc())
            .limit(top_n)
        )
        .all()
    )
    top_queries = [TopQuery(query_text=r.query_text, count=r.cnt) for r in top_q]

    # Weak match queries (zero results or top_score < threshold)
    weak_q = (
        db.execute(
            select(
                SearchEvent.query_text,
                func.count(SearchEvent.id).label("cnt"),
            )
            .where(
                SearchEvent.created_at >= cutoff,
                (SearchEvent.result_count == 0) | (SearchEvent.top_score < settings.confidence_threshold),
            )
            .group_by(SearchEvent.query_text)
            .order_by(func.count(SearchEvent.id).desc())
            .limit(top_n)
        )
        .all()
    )
    weak_match_queries = [TopQuery(query_text=r.query_text, count=r.cnt) for r in weak_q]

    # Response time stats
    all_times = db.scalars(
        select(SearchEvent.response_time_ms)
        .where(SearchEvent.created_at >= cutoff)
        .order_by(SearchEvent.response_time_ms)
    ).all()

    if all_times:
        sorted_times = sorted(all_times)
        n = len(sorted_times)
        median_ms = float(sorted_times[n // 2])
        p95_idx = min(int(n * 0.95), n - 1)
        p95_ms = float(sorted_times[p95_idx])
    else:
        median_ms = 0.0
        p95_ms = 0.0

    return AnalyticsResponse(
        top_queries=top_queries,
        weak_match_queries=weak_match_queries,
        response_time_stats=ResponseTimeStats(median_ms=median_ms, p95_ms=p95_ms),
    )


@router.get("/api/v1/admin/index-refresh", response_model=IndexRefreshResponse)
def get_index_status(db: DbSession, _role: AdminRole):
    """Get current index status (count of indexed active steps)."""
    count = db.scalar(
        select(func.count(RunbookStep.id))
        .join(Runbook, Runbook.id == RunbookStep.runbook_id)
        .where(Runbook.lifecycle_status == "active")
    ) or 0
    return IndexRefreshResponse(status="current", steps_indexed=count)


@router.post("/api/v1/admin/index-refresh", response_model=IndexRefreshResponse)
def index_refresh(db: DbSession, _role: AdminRole):
    """Re-index all active runbook steps in the vector store."""
    try:
        from app.services.vector_store import refresh_full_index
        count = refresh_full_index(db)
    except Exception:
        count = 0
    return IndexRefreshResponse(status="completed", steps_indexed=count)
