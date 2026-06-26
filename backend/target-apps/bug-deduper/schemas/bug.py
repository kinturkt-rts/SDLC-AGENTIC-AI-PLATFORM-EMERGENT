"""Pydantic schemas for Bug endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class BugCreate(BaseModel):
    """Request body for POST /bugs."""
    title: str
    description: str


class BugUpdate(BaseModel):
    """Request body for PATCH /bugs/{id}."""
    title: Optional[str] = None
    description: Optional[str] = None


class DuplicateRequest(BaseModel):
    """Request body for POST /bugs/{id}/duplicate."""
    canonical_bug_id: str


class SimilarBug(BaseModel):
    """A similar bug entry returned in dedup results."""
    id: str
    title: str
    similarity_score: float


class BugOut(BaseModel):
    """Bug response (no embedding exposed)."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: str
    status: str
    duplicate_of: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @field_validator("id", "duplicate_of", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v


class BugCreateResponse(BaseModel):
    """Response for POST /bugs."""
    bug: BugOut
    similar_bugs: list[SimilarBug]
    likely_duplicate: bool
    top_match_id: Optional[str] = None


class BugUpdateResponse(BaseModel):
    """Response for PATCH /bugs/{id}."""
    bug: BugOut
    similar_bugs: list[SimilarBug]
    likely_duplicate: bool
