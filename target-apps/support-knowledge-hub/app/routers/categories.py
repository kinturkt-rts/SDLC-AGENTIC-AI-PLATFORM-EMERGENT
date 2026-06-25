"""Categories router."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.dependencies import DbSession, AuthenticatedUser, AuthUser, require_role
from app.models.category import Category
from schemas.category import CategoryCreate, CategoryOut, CategoryUpdate

router = APIRouter(tags=["categories"])


@router.get("/api/v1/categories", response_model=list[CategoryOut])
def list_categories(
    db: DbSession,
    current_user: AuthUser,
) -> list[CategoryOut]:
    stmt = select(Category)
    if current_user.role != "knowledge_admin":
        stmt = stmt.where(Category.is_active == True)  # noqa: E712
    rows = db.scalars(stmt).all()
    return [CategoryOut.model_validate(r) for r in rows]


@router.post("/api/v1/categories", response_model=CategoryOut, status_code=201)
def create_category(
    body: CategoryCreate,
    db: DbSession,
    current_user: AuthenticatedUser = Depends(require_role("knowledge_admin")),
) -> CategoryOut:
    cat = Category(
        name=body.name,
        created_by=current_user.user_id,
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return CategoryOut.model_validate(cat)


@router.patch("/api/v1/categories/{id}", response_model=CategoryOut)
def update_category(
    id: str,
    body: CategoryUpdate,
    db: DbSession,
    current_user: AuthenticatedUser = Depends(require_role("knowledge_admin")),
) -> CategoryOut:
    cat = db.get(Category, id)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    updates = body.model_dump(exclude_unset=True)
    for k, v in updates.items():
        setattr(cat, k, v)
    db.commit()
    db.refresh(cat)
    return CategoryOut.model_validate(cat)
