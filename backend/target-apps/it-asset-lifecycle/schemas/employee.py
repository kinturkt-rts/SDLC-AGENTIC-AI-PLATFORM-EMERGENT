"""Employee schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class EmployeeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    full_name: str
    email: str
    department: str
    manager_id: Optional[str] = None
    is_active: bool
    deactivated_at: Optional[datetime] = None

    @field_validator("id", "manager_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):  # type: ignore[no-untyped-def]
        return str(v) if v is not None else v
