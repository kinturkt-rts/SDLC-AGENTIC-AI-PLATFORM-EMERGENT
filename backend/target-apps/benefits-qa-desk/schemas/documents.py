"""Document schemas."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    status: str
    uploaded_at: Optional[str] = None
    uploader: Optional[str] = None

    @field_validator("id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v

    @field_validator("uploaded_at", mode="before")
    @classmethod
    def coerce_ts(cls, v):
        if v is None:
            return None
        return str(v)
