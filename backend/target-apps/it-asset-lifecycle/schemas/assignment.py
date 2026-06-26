"""Assignment schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class AssignRequest(BaseModel):
    employee_id: str


class ReturnRequest(BaseModel):
    condition: str  # "in_stock" or "repair"
    note: Optional[str] = None


class AssignmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    asset_id: str
    employee_id: str
    assigned_at: datetime
    returned_at: Optional[datetime] = None
    assigned_by: str
    return_condition_note: Optional[str] = None

    @field_validator("id", "asset_id", "employee_id", "assigned_by", mode="before")
    @classmethod
    def coerce_uuid(cls, v):  # type: ignore[no-untyped-def]
        return str(v) if v is not None else v
