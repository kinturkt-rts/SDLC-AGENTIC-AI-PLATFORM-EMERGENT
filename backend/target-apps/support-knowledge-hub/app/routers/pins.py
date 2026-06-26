"""Pins router."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func as sa_func

from app.dependencies import DbSession, AuthenticatedUser, AuthUser, require_role
from app.models.article import Article
from app.models.pinned_article import PinnedArticle
from schemas.pin import PinCreate, PinnedArticleOut

router = APIRouter(tags=["pins"])

MAX_PINS_PER_CATEGORY = 5


@router.get("/api/v1/pins", response_model=list[PinnedArticleOut])
def list_all_pins(
    db: DbSession,
    current_user: AuthUser,
) -> list[PinnedArticleOut]:
    """List all pinned articles."""
    stmt = (
        select(PinnedArticle)
        .join(Article, PinnedArticle.article_id == Article.id)
        .where(Article.state == "published")
        .order_by(PinnedArticle.display_order)
    )
    rows = db.scalars(stmt).all()
    return [PinnedArticleOut.model_validate(r) for r in rows]


@router.get("/api/v1/pins/{category_id}", response_model=list[PinnedArticleOut])
def list_pins(
    category_id: str,
    db: DbSession,
    current_user: AuthUser,
) -> list[PinnedArticleOut]:
    """List pinned articles for a category."""
    stmt = (
        select(PinnedArticle)
        .join(Article, PinnedArticle.article_id == Article.id)
        .where(PinnedArticle.category_id == category_id)
        .where(Article.state == "published")
        .order_by(PinnedArticle.display_order)
    )
    rows = db.scalars(stmt).all()
    return [PinnedArticleOut.model_validate(r) for r in rows]


@router.post("/api/v1/pins", response_model=PinnedArticleOut, status_code=201)
def create_pin(
    body: PinCreate,
    db: DbSession,
    current_user: AuthenticatedUser = Depends(require_role("knowledge_admin")),
) -> PinnedArticleOut:
    article = db.get(Article, body.article_id)
    if not article or article.state != "published":
        raise HTTPException(status_code=422, detail="Can only pin published articles")

    count = db.scalar(
        select(sa_func.count(PinnedArticle.id)).where(
            PinnedArticle.category_id == body.category_id
        )
    ) or 0
    if count >= MAX_PINS_PER_CATEGORY:
        raise HTTPException(
            status_code=422,
            detail=f"Maximum {MAX_PINS_PER_CATEGORY} pins per category reached",
        )

    pin = PinnedArticle(
        category_id=body.category_id,
        article_id=body.article_id,
        pinned_by=current_user.user_id,
        display_order=body.display_order,
    )
    db.add(pin)
    db.commit()
    db.refresh(pin)
    return PinnedArticleOut.model_validate(pin)


@router.delete("/api/v1/pins/{id}", status_code=204, response_model=None)
def delete_pin(
    id: str,
    db: DbSession,
    current_user: AuthenticatedUser = Depends(require_role("knowledge_admin")),
) -> None:
    pin = db.get(PinnedArticle, id)
    if not pin:
        raise HTTPException(status_code=404, detail="Pin not found")
    db.delete(pin)
    db.commit()
