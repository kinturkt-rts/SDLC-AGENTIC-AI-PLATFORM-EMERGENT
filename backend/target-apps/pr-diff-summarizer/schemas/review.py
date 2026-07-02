"""Pydantic schemas for reviews."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class ReviewCreate(BaseModel):
    """Request body for POST /reviews."""
    title: str
    diff_text: str


class ReviewOut(BaseModel):
    """Full review response."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    submitted_at: datetime
    file_count: Optional[int] = None
    lines_added: Optional[int] = None
    lines_removed: Optional[int] = None
    summary: Optional[str] = None
    risk_factors: Optional[list[str]] = None
    risk_score: Optional[int] = None
    risk_band: Optional[str] = None
    model_id: Optional[str] = None
    created_by: Optional[str] = None

    @field_validator("id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v


class ReviewListResponse(BaseModel):
    """Paginated list of reviews."""
    items: list[ReviewOut]
    total: int


class Last30Days(BaseModel):
    """Risk band counts for last 30 days."""
    low: int
    medium: int
    high: int


class StatsResponse(BaseModel):
    """Risk distribution stats for last 30 days."""
    last_30_days: Last30Days
    avg_risk_score: float
