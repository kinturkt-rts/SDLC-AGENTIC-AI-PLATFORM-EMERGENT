"""Search request/response schemas."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class SearchRequest(BaseModel):
    query: str
    category_ids: Optional[list[str]] = None
    top_n: int = 10


class SearchResultItem(BaseModel):
    article_id: str
    excerpt: str
    score: float


class SearchResponse(BaseModel):
    results: list[SearchResultItem] = []
    search_event_id: str
