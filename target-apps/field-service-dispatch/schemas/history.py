"""StatusHistory schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class HistoryEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    work_order_id: str
    actor_user_id: str
    actor_role: str
    previous_status: Optional[str] = None
    new_status: str
    context_note: Optional[str] = None
    changed_at: datetime

    @field_validator("id", "work_order_id", "actor_user_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v
