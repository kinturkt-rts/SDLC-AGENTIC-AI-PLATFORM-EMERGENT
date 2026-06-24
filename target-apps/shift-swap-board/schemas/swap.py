"""Swap request and audit schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, field_validator


class SwapCreate(BaseModel):
    offered_shift_id: str


class SwapDecision(BaseModel):
    decision_note: Optional[str] = None


class SwapOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    offered_shift_id: str
    offered_by_user_id: str
    status: str
    claimed_by_user_id: Optional[str] = None
    claimed_at: Optional[datetime] = None
    decided_by_user_id: Optional[str] = None
    decided_at: Optional[datetime] = None
    decision_note: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @field_validator(
        "id", "offered_shift_id", "offered_by_user_id",
        "claimed_by_user_id", "decided_by_user_id", mode="before"
    )
    @classmethod
    def coerce_uuid(cls, v: object) -> str | None:
        if v is None:
            return None
        return str(v)


class AuditRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    swap_request_id: str
    action: str
    actor_user_id: str
    detail: Optional[Any] = None
    created_at: datetime

    @field_validator("id", "swap_request_id", "actor_user_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v: object) -> str | None:
        if v is None:
            return None
        return str(v)
