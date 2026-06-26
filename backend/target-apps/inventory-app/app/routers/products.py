"""Products router — FR-5/6/7/8/9."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import CurrentUser, require_role
from app.models.category import Category
from app.models.product import Product
from app.models.stock_movement import StockMovement
from app.models.user import UserRole
from app.schemas.common import PaginatedResponse
from app.schemas.movement import (
    AdjustStockRequest,
    AdjustStockResponse,
    MovementOut,
)
from app.schemas.product import ProductCreate, ProductOut, ProductUpdate
from app.services import stock as stock_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/products", tags=["products"])

_admin_or_staff = require_role(UserRole.admin, UserRole.staff)
_admin_only = require_role(UserRole.admin)


# ── Listing & detail ────────────────────────────────────────────────────


@router.get(
    "",
    response_model=PaginatedResponse[ProductOut],
    dependencies=[Depends(_admin_or_staff)],
)
def list_products(
    db: Annotated[Session, Depends(get_db)],
    category_id: uuid.UUID | None = Query(None),
    sku: str | None = Query(None, max_length=64),
    low_stock: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> PaginatedResponse[ProductOut]:
    """Filtered, paginated product list (FR-6)."""
    base = select(Product)
    count_base = select(func.count(Product.id))

    if category_id is not None:
        base = base.where(Product.category_id == category_id)
        count_base = count_base.where(Product.category_id == category_id)
    if sku is not None:
        base = base.where(Product.sku == sku)
        count_base = count_base.where(Product.sku == sku)
    if low_stock:
        base = base.where(Product.qty_on_hand <= 5)
        count_base = count_base.where(Product.qty_on_hand <= 5)

    total = db.execute(count_base).scalar_one()
    rows = (
        db.execute(base.order_by(Product.created_at.desc()).limit(limit).offset(offset))
        .scalars()
        .all()
    )
    return PaginatedResponse[ProductOut](
        items=[ProductOut.model_validate(r) for r in rows],
        total=int(total),
        limit=limit,
        offset=offset,
    )


@router.post(
    "",
    response_model=ProductOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_admin_only)],
)
def create_product(
    payload: ProductCreate,
    db: Annotated[Session, Depends(get_db)],
) -> ProductOut:
    """Create a product — admin only (FR-5).

    404 when `category_id` is unknown; 409 on duplicate SKU; new products
    always start with `qty_on_hand=0`.
    """
    if db.get(Category, payload.category_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

    if (
        db.execute(select(Product).where(Product.sku == payload.sku)).scalar_one_or_none()
        is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"SKU '{payload.sku}' already exists"
        )

    product = Product(
        category_id=payload.category_id,
        sku=payload.sku,
        name=payload.name,
        unit_price=payload.unit_price,
        qty_on_hand=0,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return ProductOut.model_validate(product)


@router.get(
    "/{product_id}",
    response_model=ProductOut,
    dependencies=[Depends(_admin_or_staff)],
)
def get_product(
    product_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> ProductOut:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return ProductOut.model_validate(product)


@router.patch(
    "/{product_id}",
    response_model=ProductOut,
    dependencies=[Depends(_admin_only)],
)
def update_product(
    product_id: uuid.UUID,
    payload: ProductUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> ProductOut:
    """Partial update (FR-5). `qty_on_hand` is intentionally not in the schema.

    Pydantic ignores `qty_on_hand` if a client tries to send it because
    `ProductUpdate` does not declare that field.
    """
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    if payload.category_id is not None:
        if db.get(Category, payload.category_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Category not found"
            )
        product.category_id = payload.category_id
    if payload.name is not None:
        product.name = payload.name
    if payload.unit_price is not None:
        product.unit_price = payload.unit_price

    # Application-maintained updated_at per HANDOFF.md (no DB trigger).
    product.updated_at = datetime.now(tz=timezone.utc)
    db.commit()
    db.refresh(product)
    return ProductOut.model_validate(product)


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(_admin_only)],
)
def delete_product(
    product_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    """Delete a product — admin only (FR-9). 409 when `qty_on_hand > 0`."""
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    if product.qty_on_hand > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete product with qty_on_hand > 0",
        )
    db.delete(product)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Stock adjustment + history ─────────────────────────────────────────


@router.post(
    "/{product_id}/adjust-stock",
    response_model=AdjustStockResponse,
    dependencies=[Depends(_admin_or_staff)],
)
def adjust_stock(
    product_id: uuid.UUID,
    payload: AdjustStockRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: CurrentUser,
) -> AdjustStockResponse:
    """Atomic stock adjustment (FR-7).

    422 when the resulting `qty_on_hand` would be negative; 404 when the
    product is missing. The full operation runs in a single transaction
    so a rejected delta leaves no movement row behind (NFR-6).
    """
    try:
        result = stock_service.adjust_stock(
            db,
            product_id=product_id,
            delta=payload.delta,
            reason=payload.reason,
            note=payload.note,
            performed_by=current_user.id,
        )
    except stock_service.ProductNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found") from None
    except stock_service.NegativeStockError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from None
    except stock_service.InvalidDeltaError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from None

    return AdjustStockResponse(
        movement=MovementOut.model_validate(result.movement),
        qty_on_hand=result.new_qty,
    )


@router.get(
    "/{product_id}/movements",
    response_model=PaginatedResponse[MovementOut],
    dependencies=[Depends(_admin_or_staff)],
)
def list_movements(
    product_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> PaginatedResponse[MovementOut]:
    """Paginated movement history, newest-first (FR-8)."""
    if db.get(Product, product_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    total = db.execute(
        select(func.count(StockMovement.id)).where(StockMovement.product_id == product_id)
    ).scalar_one()
    rows = (
        db.execute(
            select(StockMovement)
            .where(StockMovement.product_id == product_id)
            .order_by(StockMovement.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )
    return PaginatedResponse[MovementOut](
        items=[MovementOut.model_validate(r) for r in rows],
        total=int(total),
        limit=limit,
        offset=offset,
    )
