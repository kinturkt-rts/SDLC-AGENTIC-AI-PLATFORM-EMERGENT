"""Change request schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class ChangeRequestCreate(BaseModel):
    title: str
    description: str
    service_id: str
    target_environment_id: str
    change_type: str  # standard|normal|emergency
    risk: str  # low|medium|high|critical
    planned_start: datetime
    planned_end: datetime
    rollback_plan: str


class StatusTransition(BaseModel):
    to_status: str
    reason: Optional[str] = None
    planned_start: Optional[datetime] = None
    planned_end: Optional[datetime] = None


class AssignRequest(BaseModel):
    implementer_id: str


class ApprovalRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    change_id: str
    approver_id: str
    decision: str
    comment: Optional[str] = None
    decided_at: Optional[datetime] = None

    @field_validator("id", "change_id", "approver_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v


class StatusHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    change_id: str
    from_status: Optional[str] = None
    to_status: str
    actor_id: str
    changed_at: Optional[datetime] = None
    reason: Optional[str] = None

    @field_validator("id", "change_id", "actor_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v


class ChangeRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: str
    service_id: str
    target_environment_id: str
    change_type: str
    risk: str
    status: str
    requester_id: str
    implementer_id: Optional[str] = None
    planned_start: Optional[datetime] = None
    planned_end: Optional[datetime] = None
    rollback_plan: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None

    @field_validator("id", "service_id", "target_environment_id", "requester_id", "implementer_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v


class ChangeRequestDetail(ChangeRequestOut):
    approval_records: list[ApprovalRecordOut] = []
    status_history: list[StatusHistoryOut] = []


class ChangeRequestListPage(BaseModel):
    items: list[ChangeRequestOut]
    total: int
    page: int
    page_size: int
