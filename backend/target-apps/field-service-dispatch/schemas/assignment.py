"""Assignment schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class AssignmentCreate(BaseModel):
    work_order_id: str
    technician_id: str


class AssignmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    work_order_id: str
    technician_id: str
    assigned_by: str
    assigned_at: datetime
    is_active: bool

    @field_validator("id", "work_order_id", "technician_id", "assigned_by", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v
