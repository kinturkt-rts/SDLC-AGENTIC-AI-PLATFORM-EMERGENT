"""Article request/response schemas."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from schemas.common import coerce_iso_datetime


class SimilarArticleItem(BaseModel):
    id: str
    title: str
    excerpt: str
    score: float


class ArticleCreate(BaseModel):
    title: str
    body: str
    category_id: str
    tags: list[str] = []


class ArticleUpdate(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    category_id: Optional[str] = None
    tags: Optional[list[str]] = None
    status: Optional[str] = None


class ArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    body: str
    category_id: str
    tags: list[str] | None = None
    author_id: str
    status: str
    created_at: str
    updated_at: str
    published_at: str | None = None
    archived_at: str | None = None

    @field_validator("id", "category_id", "author_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v

    @field_validator(
        "created_at", "updated_at", "published_at", "archived_at", mode="before"
    )
    @classmethod
    def coerce_timestamps(cls, v):
        return coerce_iso_datetime(v)

    @field_validator("tags", mode="before")
    @classmethod
    def coerce_tags(cls, v):
        if v is None:
            return []
        return v


class ArticleWithSimilar(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    body: str
    category_id: str
    tags: list[str] | None = None
    author_id: str
    status: str
    created_at: str
    updated_at: str
    published_at: str | None = None
    archived_at: str | None = None
    similar_articles: list[SimilarArticleItem] = []

    @field_validator("id", "category_id", "author_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v

    @field_validator(
        "created_at", "updated_at", "published_at", "archived_at", mode="before"
    )
    @classmethod
    def coerce_timestamps(cls, v):
        return coerce_iso_datetime(v)

    @field_validator("tags", mode="before")
    @classmethod
    def coerce_tags(cls, v):
        if v is None:
            return []
        return v


class SimilarArticlesRequest(BaseModel):
    body: str


class SimilarArticlesResponse(BaseModel):
    similar_articles: list[SimilarArticleItem] = []
