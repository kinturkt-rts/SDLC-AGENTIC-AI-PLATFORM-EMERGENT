"""Category request/response schemas."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator

from schemas.common import coerce_iso_datetime


class CategoryCreate(BaseModel):
    name: str
    slug: str


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    created_by: str
    created_at: str

    @field_validator("id", "created_by", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v

    @field_validator("created_at", mode="before")
    @classmethod
    def coerce_timestamps(cls, v):
        return coerce_iso_datetime(v)
