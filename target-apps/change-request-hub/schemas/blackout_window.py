"""Blackout window schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class BlackoutWindowCreate(BaseModel):
    environment_id: str
    start_at: datetime
    end_at: datetime
    reason: str


class BlackoutWindowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    environment_id: str
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    reason: str
    created_by: str
    created_at: Optional[datetime] = None

    @field_validator("id", "environment_id", "created_by", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v


class BlackoutWindowListPage(BaseModel):
    items: list[BlackoutWindowOut]
    total: int
    page: int
    page_size: int
