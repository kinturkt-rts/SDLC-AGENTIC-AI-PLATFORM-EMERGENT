"""Product DTOs (FR-5/6)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ProductCreate(BaseModel):
    """Request body for `POST /products`. `qty_on_hand` is **not** accepted."""

    category_id: uuid.UUID
    sku: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=120)
    unit_price: Decimal = Field(..., ge=Decimal("0"), max_digits=10, decimal_places=2)


class ProductUpdate(BaseModel):
    """Partial update — `qty_on_hand` is intentionally absent (FR-5)."""

    category_id: uuid.UUID | None = None
    name: str | None = Field(None, min_length=1, max_length=120)
    unit_price: Decimal | None = Field(
        None, ge=Decimal("0"), max_digits=10, decimal_places=2
    )


class ProductOut(BaseModel):
    """Standard product response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category_id: uuid.UUID
    sku: str
    name: str
    unit_price: Decimal
    qty_on_hand: int
    created_at: datetime
    updated_at: datetime
