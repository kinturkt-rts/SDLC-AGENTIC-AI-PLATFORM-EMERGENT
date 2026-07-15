"""Schemas for POST /api/v1/upload."""
from __future__ import annotations

from pydantic import BaseModel


class UploadResponse(BaseModel):
    message: str
    char_count: int
