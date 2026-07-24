"""User Pydantic schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    role: str
    team_id: Optional[str] = None
    created_at: datetime

    @field_validator("id", "team_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v: object) -> str | None:
        return str(v) if v is not None else None
