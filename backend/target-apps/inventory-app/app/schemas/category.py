"""Category DTOs (FR-4)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CategoryCreate(BaseModel):
    """Request body for `POST /categories`."""

    name: str = Field(..., min_length=1, max_length=80)
    slug: str | None = Field(None, min_length=1, max_length=100)


class CategoryUpdate(BaseModel):
    """Partial-update body for `PATCH /categories/{id}` — both fields optional."""

    name: str | None = Field(None, min_length=1, max_length=80)
    slug: str | None = Field(None, min_length=1, max_length=100)


class CategoryOut(BaseModel):
    """Standard category response (list + create + update)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    created_at: datetime


class CategoryDetailOut(CategoryOut):
    """Detail endpoint adds `product_count` (FR-4)."""

    product_count: int = Field(..., ge=0)
