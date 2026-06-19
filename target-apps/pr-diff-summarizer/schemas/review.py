"""Pydantic schemas for review endpoints."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, field_validator


class ReviewCreate(BaseModel):
    """Request schema for creating a new review."""
    title: str
    diff_text: str


class ReviewOut(BaseModel):
    """Response schema for review data."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    submitted_at: datetime
    title: str
    summary: str
    risk_score: int
    risk_band: str
    file_count: int
    lines_added: int
    lines_removed: int
    model_id: str
    created_by: str
    
    @field_validator("id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v


class ReviewListPage(BaseModel):
    """Paginated response schema for review list."""
    items: list[ReviewOut]
    total: int
    limit: int
    offset: int


class StatsOut(BaseModel):
    """Response schema for review statistics."""
    last_30_days: dict[str, int]  # {"low": 5, "medium": 10, "high": 3}
    avg_risk_score: float


class HealthOut(BaseModel):
    """Response schema for health check."""
    status: str
    checks: dict[str, str] = {"api": "ok", "database": "ok"}