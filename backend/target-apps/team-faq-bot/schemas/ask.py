"""Schemas for POST /api/v1/ask."""
from __future__ import annotations

from pydantic import BaseModel


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer: str
    citation: str | None = None
