"""Schemas for Admin analytics."""
from __future__ import annotations

from pydantic import BaseModel


class RelianceItem(BaseModel):
    service_name: str
    touch_count: int


class TopQuery(BaseModel):
    query_text: str
    count: int


class ResponseTimeStats(BaseModel):
    median_ms: float
    p95_ms: float


class AnalyticsResponse(BaseModel):
    top_queries: list[TopQuery]
    weak_match_queries: list[TopQuery]
    response_time_stats: ResponseTimeStats


class IndexRefreshResponse(BaseModel):
    status: str
    steps_indexed: int
