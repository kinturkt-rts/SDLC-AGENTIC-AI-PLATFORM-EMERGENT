"""Pydantic schemas for bug endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.bug import BugStatus


class BugCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: str = Field(..., min_length=1)


class BugUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = Field(default=None, min_length=1)


class SimilarBugOut(BaseModel):
    id: str
    title: str
    description: str
    similarity_score: float


class BugOut(BaseModel):
    id: str
    title: str
    description: str
    status: BugStatus
    duplicate_of_id: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BugSubmitResponse(BaseModel):
    bug: BugOut
    similar_bugs: list[SimilarBugOut]
    likely_duplicate: bool
    top_similarity_score: float | None


class MarkDuplicateRequest(BaseModel):
    duplicate_of_id: str
