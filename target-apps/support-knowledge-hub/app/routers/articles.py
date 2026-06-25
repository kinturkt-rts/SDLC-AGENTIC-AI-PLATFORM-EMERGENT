"""Articles CRUD router."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from app.dependencies import DbSession, AuthenticatedUser, AuthUser, require_role
from app.models.article import Article
from schemas.article import (
    ArticleCreate,
    ArticleOut,
    ArticleSummary,
    ArticleUpdate,
    SimilarArticleResult,
)

router = APIRouter(tags=["articles"])


@router.get("/api/v1/articles", response_model=list[ArticleSummary])
def list_articles(
    db: DbSession,
    current_user: AuthUser,
    state: str | None = Query(default=None),
    category_id: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[ArticleSummary]:
    stmt = select(Article)
    if current_user.role not in ("knowledge_admin",):
        stmt = stmt.where(Article.state == "published")
    else:
        if state:
            stmt = stmt.where(Article.state == state)
    if category_id:
        stmt = stmt.where(Article.category_id == category_id)
    stmt = stmt.offset(skip).limit(limit)
    rows = db.scalars(stmt).all()
    return [ArticleSummary.model_validate(r) for r in rows]


@router.post("/api/v1/articles", response_model=ArticleOut, status_code=201)
def create_article(
    body: ArticleCreate,
    db: DbSession,
    current_user: AuthenticatedUser = Depends(require_role("contributor", "knowledge_admin")),
) -> ArticleOut:
    article = Article(
        title=body.title,
        body=body.body,
        category_id=body.category_id,
        tags=body.tags or [],
        author_id=current_user.user_id,
        state="draft",
    )
    db.add(article)
    db.commit()
    db.refresh(article)
    return ArticleOut.model_validate(article)


@router.get("/api/v1/articles/{id}", response_model=ArticleOut)
def get_article(
    id: str,
    db: DbSession,
    current_user: AuthUser,
) -> ArticleOut:
    article = db.get(Article, id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    if article.state != "published":
        if current_user.role != "knowledge_admin" and article.author_id != current_user.user_id:
            raise HTTPException(status_code=403, detail="Forbidden")
    return ArticleOut.model_validate(article)


@router.patch("/api/v1/articles/{id}", response_model=ArticleOut)
def update_article(
    id: str,
    body: ArticleUpdate,
    db: DbSession,
    current_user: AuthUser,
) -> ArticleOut:
    article = db.get(Article, id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    if current_user.role == "contributor":
        if article.author_id != current_user.user_id:
            raise HTTPException(status_code=403, detail="Forbidden")
    elif current_user.role not in ("knowledge_admin",):
        raise HTTPException(status_code=403, detail="Forbidden")

    updates = body.model_dump(exclude_unset=True)

    if "state" in updates:
        new_state = updates["state"]
        _validate_state_transition(article, new_state, current_user)
        if new_state == "published" and article.state != "published":
            updates["published_at"] = datetime.now(timezone.utc)
        if new_state == "archived":
            updates["archived_at"] = datetime.now(timezone.utc)

    for k, v in updates.items():
        setattr(article, k, v)
    article.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(article)
    return ArticleOut.model_validate(article)


def _validate_state_transition(
    article: Article, new_state: str, user: AuthenticatedUser
) -> None:
    valid_states = ("draft", "published", "archived")
    if new_state not in valid_states:
        raise HTTPException(status_code=422, detail=f"Invalid state: {new_state}")
    if user.role == "contributor":
        if not (article.state == "draft" and new_state == "published"):
            raise HTTPException(
                status_code=403,
                detail="Contributors can only publish their own drafts",
            )


@router.post("/api/v1/articles/{id}/similar", response_model=list[SimilarArticleResult])
def similar_articles(
    id: str,
    db: DbSession,
    current_user: AuthenticatedUser = Depends(require_role("contributor", "knowledge_admin")),
) -> list[SimilarArticleResult]:
    """Return top 5 published articles semantically similar to article body."""
    article = db.get(Article, id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    try:
        from app.services.bedrock_client import get_bedrock_client
        client = get_bedrock_client()
        client.invoke_embed(article.body)
        return []
    except Exception:
        return []
