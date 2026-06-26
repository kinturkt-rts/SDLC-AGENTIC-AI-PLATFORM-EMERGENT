"""Search router."""
from __future__ import annotations

import hashlib

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.dependencies import DbSession, AuthenticatedUser, AuthUser
from app.models.article import Article
from app.models.search_log import SearchLog
from app.models.search_result_item import SearchResultItem
from schemas.search import SearchRequest, SearchResultItem as SearchResultItemSchema

router = APIRouter(tags=["search"])


@router.get("/api/v1/search", response_model=list[SearchResultItemSchema])
def list_search_history(
    db: DbSession,
    current_user: AuthUser,
    limit: int = Query(default=20, ge=1, le=100),
) -> list[SearchResultItemSchema]:
    """List recent search results (placeholder for GET list)."""
    return []


@router.post("/api/v1/search", response_model=list[SearchResultItemSchema])
def semantic_search(
    body: SearchRequest,
    db: DbSession,
    current_user: AuthUser,
) -> list[SearchResultItemSchema]:
    """Semantic search across published articles."""
    top_k = body.top_k or 10

    stmt = select(Article).where(Article.state == "published")
    if body.category_id:
        stmt = stmt.where(Article.category_id == body.category_id)

    keyword = f"%{body.query}%"
    stmt = stmt.where(
        (Article.title.ilike(keyword)) | (Article.body.ilike(keyword))
    ).limit(top_k)

    articles = db.scalars(stmt).all()

    user_id_hash = hashlib.sha256(current_user.user_id.encode()).hexdigest()
    search_log = SearchLog(
        user_id_hash=user_id_hash,
        query_text=body.query,
        category_filter=body.category_id,
        result_count=len(articles),
    )
    db.add(search_log)
    db.flush()

    results: list[SearchResultItemSchema] = []
    for rank, art in enumerate(articles, 1):
        sri = SearchResultItem(
            search_log_id=search_log.id,
            article_id=art.id,
            rank_position=rank,
        )
        db.add(sri)
        excerpt = art.body[:200] if art.body else ""
        results.append(
            SearchResultItemSchema(
                article_id=str(art.id),
                title=art.title,
                excerpt=excerpt,
                category_id=str(art.category_id),
                rank=rank,
            )
        )

    db.commit()
    return results
