"""Audit log Pydantic schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, field_validator


class AuditEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    expense_id: str
    actor_id: Optional[str] = None
    actor_role: Optional[str] = None
    action: str
    from_status: Optional[str] = None
    to_status: Optional[str] = None
    metadata_json: Optional[Any] = None
    created_at: datetime

    @field_validator("id", "expense_id", "actor_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v: object) -> str | None:
        return str(v) if v is not None else None
