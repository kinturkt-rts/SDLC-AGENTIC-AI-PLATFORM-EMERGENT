"""Audit event schemas."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class AuditEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    role_at_time: str
    action_type: str
    resource_type: str
    resource_id: Optional[str] = None
    resource_name: Optional[str] = None
    outcome: str
    question_excerpt: Optional[str] = None
    timestamp: Optional[str] = None

    @field_validator("id", "user_id", "resource_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v

    @field_validator("timestamp", mode="before")
    @classmethod
    def coerce_ts(cls, v):
        if v is None:
            return None
        return str(v)


class AuditListResponse(BaseModel):
    items: list[AuditEventOut]
    total: int
