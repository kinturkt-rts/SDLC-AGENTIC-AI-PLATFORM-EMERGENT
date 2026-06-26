"""Analytics schemas."""
from __future__ import annotations

from pydantic import BaseModel


class GapItem(BaseModel):
    query_text: str
    search_count: int
    weak_result_count: int
