"""FAQ topic schemas."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator


class FaqTopicCreate(BaseModel):
    label: str


class FaqTopicOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    label: str

    @field_validator("id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v
