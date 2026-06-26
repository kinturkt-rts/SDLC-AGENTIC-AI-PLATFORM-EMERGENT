"""Schemas for Symptom Search."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str
    service_id: Optional[str] = None
    top_k: int = Field(default=5, ge=1, le=20)


class SearchResultItem(BaseModel):
    service_name: str
    runbook_title: str
    step_number: int
    step_title: str
    excerpt: str
    summary: Optional[str] = None
    score: float


class SearchResponse(BaseModel):
    results: list[SearchResultItem]
