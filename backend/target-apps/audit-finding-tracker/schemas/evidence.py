"""Pydantic schemas for evidence file endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class EvidenceResponse(BaseModel):
    """Evidence file response model."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    finding_id: str
    filename: str
    s3_key: str
    file_size: int
    mime_type: str
    uploaded_by: str
    uploaded_at: datetime
    
    @field_validator("id", "finding_id", "uploaded_by", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v