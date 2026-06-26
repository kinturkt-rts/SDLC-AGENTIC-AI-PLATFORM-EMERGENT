"""Location schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class LocationCreate(BaseModel):
    floor: str
    area_label: Optional[str] = None


class LocationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    site_id: str
    floor: str
    area_label: Optional[str] = None
    created_at: datetime

    @field_validator("id", "site_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v else v
