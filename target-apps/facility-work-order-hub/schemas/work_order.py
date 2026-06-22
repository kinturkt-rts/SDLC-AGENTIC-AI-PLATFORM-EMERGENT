"""Work order schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class WorkOrderCreate(BaseModel):
    title: str
    description: str
    category: str
    priority: str
    site_id: str
    location_id: Optional[str] = None
    due_by: Optional[datetime] = None


class WorkOrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: str
    category: str
    priority: str
    status: str
    requester_id: str
    assignee_id: Optional[str] = None
    site_id: str
    location_id: Optional[str] = None
    due_by: Optional[datetime] = None
    reopen_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    assigned_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    is_overdue: bool = False
    warnings: Optional[list[str]] = None

    @field_validator("id", "requester_id", "assignee_id", "site_id", "location_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v else v


class WorkOrderListPage(BaseModel):
    items: list[WorkOrderOut]
    total: int
    page: int
    page_size: int


class StatusUpdateRequest(BaseModel):
    status: str
    reason: Optional[str] = None
    force_close: bool = False


class AssignRequest(BaseModel):
    assignee_id: str
