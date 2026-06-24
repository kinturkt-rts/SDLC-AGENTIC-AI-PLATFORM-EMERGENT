"""Schemas for IncidentTouch."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class IncidentTouchCreate(BaseModel):
    runbook_id: str
    step_number: Optional[int] = None
    ticket_reference: str
    notes: Optional[str] = None


class IncidentTouchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    runbook_id: str
    step_number: Optional[int] = None
    ticket_reference: str
    notes: Optional[str] = None
    role: str
    created_at: datetime

    @field_validator("id", "runbook_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v else v
