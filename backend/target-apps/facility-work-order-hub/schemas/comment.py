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
    work_order_id: str
    author_id: Optional[str] = None
    body: str
    created_at: datetime
    author_display_name: Optional[str] = None

    @field_validator("id", "work_order_id", "author_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v else v
