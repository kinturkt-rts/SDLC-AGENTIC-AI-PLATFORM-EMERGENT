"""Technician schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class TechnicianCreate(BaseModel):
    name: str
    skills: list[str] = []
    active: bool = True


class TechnicianUpdate(BaseModel):
    name: Optional[str] = None
    skills: Optional[list[str]] = None
    active: Optional[bool] = None


class TechnicianOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    skills: list[str]
    active: bool
    created_at: datetime

    @field_validator("id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v
