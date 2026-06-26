"""Blackout Pydantic schemas."""
from __future__ import annotations

import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class BlackoutCreate(BaseModel):
    desk_id: str
    starts_on: datetime.date
    ends_on: datetime.date
    reason: str


class BlackoutOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    desk_id: str
    starts_on: datetime.date
    ends_on: datetime.date
    reason: str
    created_at: datetime.datetime

    @field_validator("id", "desk_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v
