"""Schemas for GET /api/v1/gaps."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class GapItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    question_text: str
    logged_at: str
