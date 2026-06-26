"""Technician schemas."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class TechnicianOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    display_name: str
    skills: list[str] = []
    is_active: bool

    @field_validator("id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v

    @field_validator("skills", mode="before")
    @classmethod
    def coerce_skills(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            # Handle postgres array string format
            v = v.strip("{}")
            return [s.strip() for s in v.split(",") if s.strip()] if v else []
        return list(v)
