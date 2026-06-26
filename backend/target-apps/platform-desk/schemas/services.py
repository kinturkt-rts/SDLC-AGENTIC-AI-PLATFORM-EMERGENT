"""Schemas for the Services domain."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ServiceCreate(BaseModel):
    name: str
    owning_team: str
    criticality_tier: int = Field(ge=1, le=3)
    active_support: bool = True


class ServiceUpdate(BaseModel):
    name: Optional[str] = None
    owning_team: Optional[str] = None
    criticality_tier: Optional[int] = Field(default=None, ge=1, le=3)
    active_support: Optional[bool] = None


class ServiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    owning_team: str
    criticality_tier: int
    active_support: bool
    created_at: datetime

    @field_validator("id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v else v


class ServiceListPage(BaseModel):
    items: list[ServiceOut]
    total: int
    limit: int
    offset: int
