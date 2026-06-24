"""Roster schemas."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator


class RosterRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    staff_id: str
    display_name: str
    shift_date: str
    shift_window: str

    @field_validator("id", "staff_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v: object) -> str:
        return str(v) if v is not None else v  # type: ignore

    @field_validator("shift_date", mode="before")
    @classmethod
    def coerce_date(cls, v: object) -> str:
        if hasattr(v, "isoformat"):
            return v.isoformat()
        return str(v) if v is not None else v  # type: ignore
