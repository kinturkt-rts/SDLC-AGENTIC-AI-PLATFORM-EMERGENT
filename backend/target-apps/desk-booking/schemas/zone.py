"""Zone Pydantic schemas."""
from __future__ import annotations

import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class ZoneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    created_at: datetime.datetime

    @field_validator("id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v
