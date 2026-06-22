"""Site schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class SiteCreate(BaseModel):
    site_code: str
    name: str
    address_line: str
    active: bool = True


class SiteUpdate(BaseModel):
    name: Optional[str] = None
    address_line: Optional[str] = None
    active: Optional[bool] = None


class SiteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    site_code: str
    name: str
    address_line: str
    active: bool
    created_at: datetime
    updated_at: datetime

    @field_validator("id", mode="before")
    @classmethod
    def coerce_id(cls, v):
        return str(v) if v else v
