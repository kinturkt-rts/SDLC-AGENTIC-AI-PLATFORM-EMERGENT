"""Pydantic schemas for completion records."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class CompletionCreate(BaseModel):
    employee_id: str
    course_id: str
    completion_date: date


class CompletionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    employee_id: str
    course_id: str
    completion_date: date
    expiry_date: Optional[date] = None
    is_active_record: bool
    superseded_by_id: Optional[str] = None
    created_at: Optional[datetime] = None

    @field_validator("id", "employee_id", "course_id", "superseded_by_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v
