"""Analytics response schemas."""
from __future__ import annotations

from pydantic import BaseModel


class GapItem(BaseModel):
    query_text: str
    count: int
    helpful_rate: float


class GapsResponse(BaseModel):
    gaps: list[GapItem] = []
