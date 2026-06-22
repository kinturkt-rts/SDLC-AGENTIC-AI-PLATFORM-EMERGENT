"""Pinned article schemas."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator

from schemas.common import coerce_iso_datetime


class PinCreate(BaseModel):
    article_id: str


class PinnedArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    category_id: str
    article_id: str
    pinned_by: str
    pinned_at: str

    @field_validator("id", "category_id", "article_id", "pinned_by", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v

    @field_validator("pinned_at", mode="before")
    @classmethod
    def coerce_timestamps(cls, v):
        return coerce_iso_datetime(v)
