"""Desk Pydantic schemas."""
from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class DeskCreate(BaseModel):
    zone: str  # zone name (north|south|lab)
    label: str


class DeskUpdate(BaseModel):
    zone: Optional[str] = None
    label: Optional[str] = None
    is_active: Optional[bool] = None


class DeskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    zone_id: str
    label: str
    is_active: bool
    created_at: datetime.datetime

    @field_validator("id", "zone_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v


class DeskAvailability(BaseModel):
    desk_id: str
    label: str
    zone_name: str
    available_slots: list[str]
