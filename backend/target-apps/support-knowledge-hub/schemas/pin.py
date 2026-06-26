"""PinnedArticle schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class PinCreate(BaseModel):
    category_id: str
    article_id: str
    display_order: int


class PinnedArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    category_id: str
    article_id: str
    pinned_by: str
    pinned_at: Optional[datetime] = None
    display_order: int

    @field_validator("id", "category_id", "article_id", "pinned_by", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v
