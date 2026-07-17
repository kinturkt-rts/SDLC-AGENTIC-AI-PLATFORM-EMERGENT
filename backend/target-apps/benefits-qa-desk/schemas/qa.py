"""Q&A schemas."""
from __future__ import annotations

from pydantic import BaseModel


class AskRequest(BaseModel):
    question: str


class Citation(BaseModel):
    filename: str
    snippet: str


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation] = []
