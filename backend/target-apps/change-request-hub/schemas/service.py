"""Service schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class ServiceCreate(BaseModel):
    name: str
    owner_team: str
    tier: str  # tier1|tier2|tier3


class ServiceUpdate(BaseModel):
    name: Optional[str] = None
    owner_team: Optional[str] = None
    tier: Optional[str] = None
    active: Optional[bool] = None


class ServiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    owner_team: str
    tier: str
    active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @field_validator("id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v


class ServiceListPage(BaseModel):
    items: list[ServiceOut]
    total: int
    page: int
    page_size: int
