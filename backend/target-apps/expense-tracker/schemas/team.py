"""Team Pydantic schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TeamCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None


class TeamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: Optional[str] = None
    created_at: datetime

    @field_validator("id", mode="before")
    @classmethod
    def coerce_uuid(cls, v: object) -> str | None:
        return str(v) if v is not None else None


class MemberAction(BaseModel):
    user_id: str
    action: str = Field(...)

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        allowed = {"assign", "remove"}
        if v.lower() not in allowed:
            raise ValueError(f"action must be one of: {', '.join(sorted(allowed))}")
        return v.lower()
