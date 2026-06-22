"""Articles router — CRUD + lifecycle + similarity."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.dependencies import (
    CurrentUser,
    DbSession,
    require_contributor,
)
from app.models.article import Article
from app.models.user import User
from app.services.similarity import compute_similar_articles
from schemas.article import (
    ArticleCreate,
    ArticleOut,
    ArticleUpdate,
    ArticleWithSimilar,
    SimilarArticleItem,
    SimilarArticlesRequest,
    SimilarArticlesResponse,
)

router = APIRouter(tags=["articles"])


@router.post("", response_model=ArticleOut, status_code=201)
def create_article(
    body: ArticleCreate,
    db: DbSession,
    current_user: User = Depends(require_contributor),
) -> Article:
    """Create a new article in draft state (contributor+)."""
    now = datetime.now(timezone.utc)
    article = Article(
        id=str(uuid.uuid4()),
        title=body.title,
        body=body.body,
        category_id=body.category_id,
        tags=body.tags,
        author_id=str(current_user.id),
        status="draft",
        created_at=now,
        updated_at=now,
    )
    db.add(article)
    db.commit()
    db.refresh(article)
    return article


@router.patch("/{article_id}", response_model=ArticleWithSimilar)
def update_article(
    article_id: str,
    body: ArticleUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """Update an article. Triggers similarity check on body change. (contributor+)"""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    # Permission: only author or knowledge_admin can edit
    if current_user.role not in ("knowledge_admin",) and str(article.author_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Forbidden")

    # Only knowledge_admin may archive another user's article or edit another user's published body
    if body.status == "archived" and str(article.author_id) != str(current_user.id):
        if current_user.role != "knowledge_admin":
            raise HTTPException(status_code=403, detail="Forbidden")

    updates = body.model_dump(exclude_unset=True)
    now = datetime.now(timezone.utc)

    for k, v in updates.items():
        if k == "status":
            if v == "published":
                # Validate required fields for publish
                title = updates.get("title", article.title)
                art_body = updates.get("body", article.body)
                cat_id = updates.get("category_id", article.category_id)
                if not title or not art_body or not cat_id:
                    raise HTTPException(status_code=422, detail="Title, body, and category_id required for publish")
                setattr(article, "published_at", now)
            elif v == "archived":
                setattr(article, "archived_at", now)
        setattr(article, k, v)

    article.updated_at = now
    db.commit()
    db.refresh(article)

    # Compute similarity if body was updated or status set to published
    similar: list[SimilarArticleItem] = []
    if "body" in updates or updates.get("status") == "published":
        similar = compute_similar_articles(db, article)

    result = {
        "id": str(article.id),
        "title": article.title,
        "body": article.body,
        "category_id": str(article.category_id),
        "tags": article.tags or [],
        "author_id": str(article.author_id),
        "status": article.status,
        "created_at": article.created_at,
        "updated_at": article.updated_at,
        "published_at": article.published_at,
        "archived_at": article.archived_at,
        "similar_articles": similar,
    }
    return result


@router.get("", response_model=list[ArticleOut])
def list_articles(
    db: DbSession,
    current_user: CurrentUser,
    status: str | None = Query(default=None),
    category_id: str | None = Query(default=None),
    q: str | None = Query(default=None),
) -> list[Article]:
    """List articles. Employee sees published only; admin sees all."""
    query = db.query(Article)

    if current_user.role in ("employee", "leadership"):
        query = query.filter(Article.status == "published")
    elif current_user.role == "contributor":
        # Contributors see published + their own drafts
        from sqlalchemy import or_
        query = query.filter(
            or_(
                Article.status == "published",
                Article.author_id == str(current_user.id),
            )
        )
    # knowledge_admin sees all

    if status:
        query = query.filter(Article.status == status)
    if category_id:
        query = query.filter(Article.category_id == category_id)
    if q:
        query = query.filter(Article.title.ilike(f"%{q}%"))

    return list(query.all())


@router.get("/{article_id}", response_model=ArticleOut)
def get_article(
    article_id: str,
    db: DbSession,
    current_user: CurrentUser,
) -> Article:
    """Get single article. Employee sees published only; author/admin any."""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    # Access control
    if article.status != "published":
        if current_user.role not in ("knowledge_admin",) and str(article.author_id) != str(current_user.id):
            raise HTTPException(status_code=404, detail="Article not found")

    return article


@router.post("/{article_id}/similar", response_model=SimilarArticlesResponse)
def similar_articles(
    article_id: str,
    body: SimilarArticlesRequest,
    db: DbSession,
    current_user: User = Depends(require_contributor),
) -> SimilarArticlesResponse:
    """Compute similar published articles for a body text (contributor+)."""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    # Create a temporary article-like object for similarity computation
    class _TempArticle:
        def __init__(self, id: str, body: str):
            self.id = id
            self.body = body

    temp = _TempArticle(id=str(article.id), body=body.body)
    similar = compute_similar_articles(db, temp)  # type: ignore
    return SimilarArticlesResponse(similar_articles=similar)
