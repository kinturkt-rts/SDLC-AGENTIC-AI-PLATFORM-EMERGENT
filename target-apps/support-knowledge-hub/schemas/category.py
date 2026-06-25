"""Category schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class CategoryCreate(BaseModel):
    name: str


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    is_active: bool
    created_at: Optional[datetime] = None
    created_by: Optional[str] = None

    @field_validator("id", "created_by", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v
