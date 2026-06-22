"""Categories router."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.dependencies import DbSession, require_knowledge_admin
from app.models.article import Article
from app.models.category import Category
from app.models.pinned_article import PinnedArticle
from app.models.user import User
from schemas.category import CategoryCreate, CategoryOut
from schemas.pinned import PinCreate, PinnedArticleOut

router = APIRouter(tags=["categories"])


@router.post("", response_model=CategoryOut, status_code=201)
def create_category(
    body: CategoryCreate,
    db: DbSession,
    current_user: User = Depends(require_knowledge_admin),
) -> Category:
    """Create a new category (knowledge_admin only)."""
    now = datetime.now(timezone.utc)
    category = Category(
        id=str(uuid.uuid4()),
        name=body.name,
        slug=body.slug,
        created_by=str(current_user.id),
        created_at=now,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.delete("/{category_id}", status_code=204, response_model=None)
def delete_category(
    category_id: str,
    db: DbSession,
    current_user: User = Depends(require_knowledge_admin),
) -> None:
    """Delete a category. Blocked if published articles reference it (409)."""
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    blocking = (
        db.query(Article)
        .filter(Article.category_id == category_id, Article.status == "published")
        .all()
    )
    if blocking:
        blocking_ids = [str(a.id) for a in blocking]
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete category: published articles reference it: {blocking_ids}",
        )

    db.delete(category)
    db.commit()


@router.post("/{category_id}/pins", response_model=PinnedArticleOut, status_code=201)
def pin_article(
    category_id: str,
    body: PinCreate,
    db: DbSession,
    current_user: User = Depends(require_knowledge_admin),
) -> PinnedArticle:
    """Pin an article to a category (max 5, published only)."""
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    article = db.query(Article).filter(Article.id == body.article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    if article.status != "published":
        raise HTTPException(status_code=422, detail="Only published articles may be pinned")

    pin_count = db.query(PinnedArticle).filter(PinnedArticle.category_id == category_id).count()
    if pin_count >= 5:
        raise HTTPException(status_code=422, detail="Maximum 5 pinned articles per category")

    now = datetime.now(timezone.utc)
    pin = PinnedArticle(
        id=str(uuid.uuid4()),
        category_id=category_id,
        article_id=body.article_id,
        pinned_by=str(current_user.id),
        pinned_at=now,
    )
    db.add(pin)
    db.commit()
    db.refresh(pin)
    return pin
