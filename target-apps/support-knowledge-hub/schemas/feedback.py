"""Feedback request/response schemas."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator


class FeedbackCreate(BaseModel):
    search_event_id: str
    article_id: str
    rating: str


class FeedbackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    rating: str

    @field_validator("id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v
