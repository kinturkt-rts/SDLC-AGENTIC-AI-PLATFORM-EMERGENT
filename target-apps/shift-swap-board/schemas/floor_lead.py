"""Floor lead week schemas."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator


class FloorLeadWeekCreate(BaseModel):
    week_start: str  # ISO date (must be Monday)
    floor_lead_user_id: str


class FloorLeadWeekOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    week_start: str
    floor_lead_user_id: str

    @field_validator("id", "floor_lead_user_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v: object) -> str | None:
        if v is None:
            return None
        return str(v)

    @field_validator("week_start", mode="before")
    @classmethod
    def coerce_date(cls, v: object) -> str:
        if hasattr(v, "isoformat"):
            return v.isoformat()
        return str(v) if v is not None else v  # type: ignore
