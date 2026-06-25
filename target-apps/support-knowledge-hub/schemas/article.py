"""Article schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class ArticleCreate(BaseModel):
    title: str
    body: str
    category_id: str
    tags: Optional[list[str]] = None


class ArticleUpdate(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    category_id: Optional[str] = None
    tags: Optional[list[str]] = None
    state: Optional[str] = None


class ArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    body: str
    category_id: str
    tags: Optional[list[str]] = None
    author_id: str
    state: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    archived_at: Optional[datetime] = None

    @field_validator("id", "category_id", "author_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v


class ArticleSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    category_id: str
    author_id: str
    state: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @field_validator("id", "category_id", "author_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v


class SimilarArticleResult(BaseModel):
    article_id: str
    title: str
    score: float
