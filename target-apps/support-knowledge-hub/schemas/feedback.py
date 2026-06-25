"""Feedback schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class FeedbackCreate(BaseModel):
    search_log_id: str
    article_id: str
    signal: str


class FeedbackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    search_log_id: str
    article_id: str
    user_id_hash: str
    signal: str
    created_at: Optional[datetime] = None

    @field_validator("id", "search_log_id", "article_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v
