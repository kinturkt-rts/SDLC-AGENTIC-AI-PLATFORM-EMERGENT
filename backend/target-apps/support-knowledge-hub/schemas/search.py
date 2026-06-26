"""Search schemas."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class SearchRequest(BaseModel):
    query: str
    category_id: Optional[str] = None
    top_k: Optional[int] = 10


class SearchResultItem(BaseModel):
    article_id: str
    title: str
    excerpt: str
    category_id: str
    rank: int
