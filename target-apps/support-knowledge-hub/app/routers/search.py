"""Search router."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter

from app.dependencies import CurrentUser, DbSession
from app.models.article import Article
from app.models.search_event import SearchEvent
from schemas.search import SearchRequest, SearchResponse, SearchResultItem

router = APIRouter(tags=["search"])


@router.post("", response_model=SearchResponse, status_code=201)
def search_articles(
    body: SearchRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> SearchResponse:
    """Semantic search over published articles. Logs a SearchEvent."""
    query = db.query(Article).filter(Article.status == "published")

    if body.category_ids:
        query = query.filter(Article.category_id.in_(body.category_ids))

    # Naive keyword fallback (semantic search requires embeddings service in prod)
    articles = query.all()
    results: list[SearchResultItem] = []
    q_lower = body.query.lower()

    for art in articles:
        # Simple text match scoring for MVP (semantic would use embeddings)
        title_score = 0.0
        body_score = 0.0
        if q_lower in (art.title or "").lower():
            title_score = 0.8
        if q_lower in (art.body or "").lower():
            body_score = 0.6
        score = max(title_score, body_score)
        if score > 0:
            excerpt = (art.body or "")[:200]
            results.append(SearchResultItem(
                article_id=str(art.id),
                excerpt=excerpt,
                score=score,
            ))

    # Sort by score desc, limit
    results.sort(key=lambda r: r.score, reverse=True)
    results = results[:body.top_n]

    # Log search event
    now = datetime.now(timezone.utc)
    event_id = str(uuid.uuid4())
    search_event = SearchEvent(
        id=event_id,
        query_text=body.query,
        result_article_ids=[r.article_id for r in results],
        result_count=len(results),
        role=current_user.role,
        timestamp=now,
    )
    db.add(search_event)
    db.commit()

    return SearchResponse(results=results, search_event_id=event_id)
