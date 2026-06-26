"""Pydantic v2 schemas for Notice endpoints."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CreateNoticeRequest(BaseModel):
    title: str = Field(..., max_length=200)
    body: str
    category_id: Optional[int] = None
    author_display_name: str = Field(..., max_length=100)
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class UpdateNoticeRequest(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)
    body: Optional[str] = None
    category_id: Optional[int] = None
    author_display_name: Optional[str] = Field(default=None, max_length=100)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    archived: Optional[bool] = None


class NoticeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    body: str
    category_id: Optional[int] = None
    author_display_name: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    archived: bool
    created_at: datetime
    updated_at: datetime


class NoticeListResponse(BaseModel):
    items: list[NoticeResponse]
    total: int
    page: int
    limit: int
    pages: int


class StatusResponse(BaseModel):
    status: str
    message: str
