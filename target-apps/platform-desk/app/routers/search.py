"""Symptom search — semantic search over active runbook steps."""
from __future__ import annotations

import time

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.config import get_settings
from app.dependencies import DbSession, ViewerRole
from app.models.search_event import SearchEvent
from schemas.search import SearchRequest, SearchResponse, SearchResultItem

router = APIRouter(tags=["search"])


@router.get("/api/v1/search", response_model=SearchResponse)
def list_recent_searches(
    db: DbSession,
    _role: ViewerRole,
    limit: int = Query(default=10, ge=1, le=50),
):
    """List recent search events (for Streamlit display). Returns empty results array."""
    return SearchResponse(results=[])


@router.post("/api/v1/search", response_model=SearchResponse)
def search_runbooks(body: SearchRequest, db: DbSession, _role: ViewerRole):
    start_ms = time.time()
    settings = get_settings()
    results: list[SearchResultItem] = []

    try:
        from app.services.vector_store import query_steps
        raw_results = query_steps(
            query=body.query,
            service_id=body.service_id,
            top_k=body.top_k * 3,  # over-fetch for deduplication
        )
    except Exception:
        raw_results = []

    # Deduplicate: one result per runbook (highest score)
    seen_runbooks: dict[str, dict] = {}
    for item in raw_results:
        rb_id = item["runbook_id"]
        if rb_id not in seen_runbooks or item["score"] > seen_runbooks[rb_id]["score"]:
            seen_runbooks[rb_id] = item

    sorted_results = sorted(seen_runbooks.values(), key=lambda x: x["score"], reverse=True)[:body.top_k]

    for item in sorted_results:
        # Low-confidence disclosure
        summary = item.get("excerpt", "")[:100]
        if item["score"] < settings.confidence_threshold:
            summary = "Confidence is low \u2014 review steps carefully"
        results.append(SearchResultItem(
            service_name=item.get("service_name", ""),
            runbook_title=item.get("runbook_title", ""),
            step_number=item.get("step_number", 0),
            step_title=item.get("step_title", ""),
            excerpt=item.get("excerpt", ""),
            summary=summary,
            score=round(item["score"], 4),
        ))

    elapsed_ms = int((time.time() - start_ms) * 1000)
    top_score = results[0].score if results else 0.0

    # Log search event
    event = SearchEvent(
        query_text=body.query[:500],
        service_filter_id=body.service_id,
        result_count=len(results),
        top_score=top_score,
        response_time_ms=elapsed_ms,
    )
    db.add(event)
    db.commit()

    return SearchResponse(results=results)
