"""Schemas for the Runbooks domain."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class RunbookCreate(BaseModel):
    title: str
    service_id: str
    default_severity: str
    short_summary: Optional[str] = None
    author: str


class RunbookOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    service_id: str
    default_severity: str
    short_summary: Optional[str] = None
    author: str
    lifecycle_status: str
    created_at: datetime
    updated_at: datetime

    @field_validator("id", "service_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v else v


class RunbookListPage(BaseModel):
    items: list[RunbookOut]
    total: int
    limit: int
    offset: int


class SimilarRunbook(BaseModel):
    runbook_id: str
    title: str
    score: float


class ActivationResponse(BaseModel):
    status: str
    similar_runbooks: list[SimilarRunbook] = []
