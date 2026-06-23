"""Category request/response schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class CategoryBase(BaseModel):
    """Shared category fields."""
    
    name: str
    description: str | None = None


class CategoryCreate(CategoryBase):
    """Request schema for creating a category."""
    pass


class CategoryUpdate(BaseModel):
    """Request schema for updating a category."""
    
    name: str | None = None
    description: str | None = None


class CategoryOut(CategoryBase):
    """Response schema for category data."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    created_at: datetime
    
    @field_validator("id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v