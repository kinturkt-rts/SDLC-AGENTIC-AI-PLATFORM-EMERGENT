"""Alerts and reports schemas."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class OffboardingAlert(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    employee_id: str
    full_name: str
    email: str
    department: str
    deactivated_at: Optional[datetime] = None
    active_assets: list[dict]

    @field_validator("employee_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):  # type: ignore[no-untyped-def]
        return str(v) if v is not None else v


class LicenseOverageAlert(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    asset_id: str
    manufacturer: str
    model: str
    seats_purchased: int
    seats_in_use: int

    @field_validator("asset_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):  # type: ignore[no-untyped-def]
        return str(v) if v is not None else v


class ValuationByDepartment(BaseModel):
    department: str
    total_cost: Decimal
    asset_count: int
