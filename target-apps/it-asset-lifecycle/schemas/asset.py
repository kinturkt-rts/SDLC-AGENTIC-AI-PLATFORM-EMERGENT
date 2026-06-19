"""Asset schemas."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class AssetCreate(BaseModel):
    asset_type: str
    manufacturer: str
    model: str
    serial_number: Optional[str] = None
    license_key: Optional[str] = None  # plaintext; encrypted on write
    seats_purchased: Optional[int] = None
    purchase_date: date
    purchase_cost: Decimal
    warranty_end_date: Optional[date] = None


class AssetUpdate(BaseModel):
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    license_key: Optional[str] = None
    seats_purchased: Optional[int] = None
    warranty_end_date: Optional[date] = None


class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    asset_type: str
    manufacturer: str
    model: str
    serial_number: Optional[str] = None
    license_key_last4: Optional[str] = None
    seats_purchased: Optional[int] = None
    purchase_date: date
    purchase_cost: Decimal
    warranty_end_date: Optional[date] = None
    status: str
    created_at: datetime
    updated_at: datetime

    @field_validator("id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):  # type: ignore[no-untyped-def]
        return str(v) if v is not None else v
