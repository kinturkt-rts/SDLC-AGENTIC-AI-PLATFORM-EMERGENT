"""Schemas for RunbookSteps."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class StepCreate(BaseModel):
    step_number: int
    title: str
    body_text: str
    estimated_minutes: Optional[int] = None
    warning_callout: Optional[str] = None


class StepUpdate(BaseModel):
    step_number: Optional[int] = None
    title: Optional[str] = None
    body_text: Optional[str] = None
    estimated_minutes: Optional[int] = None
    warning_callout: Optional[str] = None


class StepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    runbook_id: str
    step_number: int
    title: str
    body_text: str
    estimated_minutes: Optional[int] = None
    warning_callout: Optional[str] = None

    @field_validator("id", "runbook_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v else v
