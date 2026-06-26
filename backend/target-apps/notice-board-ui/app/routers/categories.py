"""Category routes — GET /api/v1/categories, POST."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.dependencies import DbSession, OrganizerAuth
from app.models.category import Category
from app.services.audit import log_operation
from schemas.category import CategoryListResponse, CategoryResponse, CreateCategoryRequest

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("", response_model=CategoryListResponse)
def list_categories(db: DbSession) -> CategoryListResponse:
    """Return all categories (for dropdowns etc.)."""
    rows = db.scalars(select(Category).order_by(Category.name)).all()
    return CategoryListResponse(items=list(rows), total=len(rows))


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    db: DbSession,
    body: CreateCategoryRequest,
    _auth: OrganizerAuth,
) -> CategoryResponse:
    """Create a new category. Requires organizer secret."""
    category = Category(name=body.name, description=body.description)
    db.add(category)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Category with name '{body.name}' already exists",
        )
    log_operation(db, "categories", "CREATE", category.id)
    db.commit()
    db.refresh(category)
    logger.info("category_created id=%s name=%s", category.id, category.name)
    return category  # type: ignore[return-value]
