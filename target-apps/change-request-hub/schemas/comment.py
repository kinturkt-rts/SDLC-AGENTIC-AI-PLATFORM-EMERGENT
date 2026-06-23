"""Comment schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class CommentCreate(BaseModel):
    body: str


class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    change_id: str
    author_id: str
    body: str
    posted_at: Optional[datetime] = None

    @field_validator("id", "change_id", "author_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v


class CommentListPage(BaseModel):
    items: list[CommentOut]
    total: int
    page: int
    page_size: int
