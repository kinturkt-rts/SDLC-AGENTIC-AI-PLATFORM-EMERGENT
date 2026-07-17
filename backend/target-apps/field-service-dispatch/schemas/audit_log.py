"""Audit log schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    work_order_id: str
    from_status: Optional[str] = None
    to_status: str
    actor_id: str
    actor_role: str
    changed_at: datetime

    @field_validator("id", "work_order_id", "actor_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v
