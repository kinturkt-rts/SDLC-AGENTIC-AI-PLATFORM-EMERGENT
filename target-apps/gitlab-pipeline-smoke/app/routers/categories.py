"""Category management endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.dependencies import AuthKey, DbSession
from app.models import Category
from schemas.category import CategoryCreate, CategoryOut, CategoryUpdate

router = APIRouter()


@router.post("/", response_model=CategoryOut, status_code=201)
def create_category(
    body: CategoryCreate,
    db: DbSession,
    _auth_key: AuthKey,
) -> Category:
    """Create a new category (requires API key)."""
    category = Category(
        name=body.name,
        description=body.description,
    )
    db.add(category)
    try:
        db.commit()
        db.refresh(category)
        return category
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Category name '{body.name}' already exists",
        )


@router.get("/", response_model=list[CategoryOut])
def list_categories(db: DbSession) -> list[Category]:
    """List all categories ordered by name."""
    return list(db.scalars(select(Category).order_by(Category.name)).all())


@router.get("/{id}", response_model=CategoryOut)
def get_category(id: str, db: DbSession) -> Category:
    """Get category by ID."""
    category = db.get(Category, id)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )
    return category


@router.patch("/{id}", response_model=CategoryOut)
def update_category(
    id: str,
    body: CategoryUpdate,
    db: DbSession,
    _auth_key: AuthKey,
) -> Category:
    """Update category (requires API key)."""
    category = db.get(Category, id)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )
    
    # Apply updates
    updates = body.model_dump(exclude_unset=True)
    for k, v in updates.items():
        setattr(category, k, v)
    
    try:
        db.commit()
        db.refresh(category)
        return category
    except IntegrityError:
        db.rollback()
        if body.name:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Category name '{body.name}' already exists",
            )
        raise