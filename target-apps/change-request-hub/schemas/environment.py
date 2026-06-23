"""Environment schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class EnvironmentCreate(BaseModel):
    name: str
    sort_order: int


class EnvironmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    sort_order: int
    active: bool
    created_at: Optional[datetime] = None

    @field_validator("id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v


class EnvironmentListPage(BaseModel):
    items: list[EnvironmentOut]
    total: int
    page: int
    page_size: int
