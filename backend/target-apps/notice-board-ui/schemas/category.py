"""Pydantic v2 schemas for Category endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CreateCategoryRequest(BaseModel):
    name: str = Field(..., max_length=100)
    description: Optional[str] = None


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str] = None
    created_at: datetime


class CategoryListResponse(BaseModel):
    items: list[CategoryResponse]
    total: int
