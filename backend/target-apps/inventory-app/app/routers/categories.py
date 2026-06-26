"""Categories router — FR-4."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_role
from app.models.category import Category
from app.models.product import Product
from app.models.user import UserRole
from app.schemas.category import (
    CategoryCreate,
    CategoryDetailOut,
    CategoryOut,
    CategoryUpdate,
)
from app.schemas.common import PaginatedResponse
from app.security import slugify

router = APIRouter(prefix="/categories", tags=["categories"])

# Role-guards reused across handlers so behaviour is uniform.
_admin_or_staff = require_role(UserRole.admin, UserRole.staff)
_admin_only = require_role(UserRole.admin)


@router.get(
    "",
    response_model=PaginatedResponse[CategoryOut],
    dependencies=[Depends(_admin_or_staff)],
)
def list_categories(
    db: Annotated[Session, Depends(get_db)],
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> PaginatedResponse[CategoryOut]:
    """Paginated category listing — admin + staff (FR-4)."""
    total = db.execute(select(func.count(Category.id))).scalar_one()
    rows = (
        db.execute(
            select(Category).order_by(Category.created_at.desc()).limit(limit).offset(offset)
        )
        .scalars()
        .all()
    )
    return PaginatedResponse[CategoryOut](
        items=[CategoryOut.model_validate(r) for r in rows],
        total=int(total),
        limit=limit,
        offset=offset,
    )


@router.post(
    "",
    response_model=CategoryOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_admin_only)],
)
def create_category(
    payload: CategoryCreate,
    db: Annotated[Session, Depends(get_db)],
) -> CategoryOut:
    """Create a category — admin only. Auto-derives slug, 409 on duplicate."""
    slug = (payload.slug or slugify(payload.name)).strip().lower()

    existing = db.execute(select(Category).where(Category.slug == slug)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Category slug '{slug}' already exists",
        )

    cat = Category(name=payload.name, slug=slug)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return CategoryOut.model_validate(cat)


@router.get(
    "/{category_id}",
    response_model=CategoryDetailOut,
    dependencies=[Depends(_admin_or_staff)],
)
def get_category(
    category_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> CategoryDetailOut:
    """Detail with product_count aggregate (FR-4)."""
    cat = db.get(Category, category_id)
    if cat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

    product_count = db.execute(
        select(func.count(Product.id)).where(Product.category_id == category_id)
    ).scalar_one()

    return CategoryDetailOut(
        id=cat.id,
        name=cat.name,
        slug=cat.slug,
        created_at=cat.created_at,
        product_count=int(product_count),
    )


@router.patch(
    "/{category_id}",
    response_model=CategoryOut,
    dependencies=[Depends(_admin_only)],
)
def update_category(
    category_id: uuid.UUID,
    payload: CategoryUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> CategoryOut:
    """Partial update — admin only. 409 on slug conflict, 404 when missing."""
    cat = db.get(Category, category_id)
    if cat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

    if payload.name is not None:
        cat.name = payload.name

    if payload.slug is not None:
        new_slug = payload.slug.strip().lower()
        if new_slug != cat.slug:
            clash = db.execute(
                select(Category).where(Category.slug == new_slug, Category.id != category_id)
            ).scalar_one_or_none()
            if clash is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Category slug '{new_slug}' already exists",
                )
            cat.slug = new_slug

    db.commit()
    db.refresh(cat)
    return CategoryOut.model_validate(cat)
