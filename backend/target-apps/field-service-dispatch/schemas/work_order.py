"""Work order schemas."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class PartInput(BaseModel):
    name: str
    quantity: int
    unit_cost: Optional[float] = None


class PartOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    work_order_id: str
    name: str
    quantity: int
    unit_cost: Optional[float] = None
    created_at: datetime

    @field_validator("id", "work_order_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v


class WorkOrderCreate(BaseModel):
    customer_id: str
    description: str
    priority: str  # routine / urgent
    scheduled_date: date
    time_window: str  # morning / afternoon / all_day


class StatusUpdate(BaseModel):
    status: str
    completion_notes: Optional[str] = None
    parts: Optional[list[PartInput]] = None


class AddendumUpdate(BaseModel):
    dispatcher_addendum: str


class WorkOrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    customer_id: str
    description: str
    priority: str
    scheduled_date: date
    time_window: str
    status: str
    completion_notes: Optional[str] = None
    dispatcher_addendum: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @field_validator("id", "customer_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v
