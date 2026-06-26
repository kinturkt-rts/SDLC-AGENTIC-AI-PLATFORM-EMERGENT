"""WorkOrder and WorkOrderPart schemas."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class WorkOrderPartCreate(BaseModel):
    part_name: str
    quantity: int
    unit_cost: Optional[Decimal] = None


class WorkOrderPartOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    work_order_id: str
    part_name: str
    quantity: int
    unit_cost: Optional[Decimal] = None

    @field_validator("id", "work_order_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v


class WorkOrderCreate(BaseModel):
    customer_id: str
    description: str
    priority: str  # routine, urgent
    scheduled_date: date
    time_window: str  # morning, afternoon, all_day


class WorkOrderPatch(BaseModel):
    status: Optional[str] = None
    assigned_technician_id: Optional[str] = None
    completion_notes: Optional[str] = None
    parts: Optional[list[WorkOrderPartCreate]] = None
    addendum: Optional[str] = None


class WorkOrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    customer_id: str
    description: str
    priority: str
    scheduled_date: date
    time_window: str
    status: str
    assigned_technician_id: Optional[str] = None
    completion_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    parts: list[WorkOrderPartOut] = []

    @field_validator("id", "customer_id", "assigned_technician_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v
