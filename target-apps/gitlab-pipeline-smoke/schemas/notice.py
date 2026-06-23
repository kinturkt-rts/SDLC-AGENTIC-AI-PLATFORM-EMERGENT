"""Notice request/response schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class NoticeBase(BaseModel):
    """Shared notice fields."""
    
    title: str
    body: str
    author_name: str
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class NoticeCreate(NoticeBase):
    """Request schema for creating a notice."""
    
    category_id: str


class NoticeUpdate(BaseModel):
    """Request schema for updating a notice."""
    
    category_id: str | None = None
    title: str | None = None
    body: str | None = None
    author_name: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class NoticeOut(NoticeBase):
    """Response schema for notice data."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    category_id: str
    is_archived: bool
    created_at: datetime
    updated_at: datetime
    
    @field_validator("id", "category_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v


class NoticeListPage(BaseModel):
    """Paginated list of notices."""
    
    items: list[NoticeOut]
    total: int
    limit: int
    offset: int