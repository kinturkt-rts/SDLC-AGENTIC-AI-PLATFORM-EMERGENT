"""FX Snapshot Pydantic schemas."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FxSnapshotCreate(BaseModel):
    currency: str = Field(..., min_length=3, max_length=3)
    date: date
    rate_to_usd: Decimal = Field(..., gt=0)

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, v: str) -> str:
        return v.upper()


class FxSnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    currency: str
    date: date
    rate_to_usd: Decimal

    @field_validator("id", mode="before")
    @classmethod
    def coerce_uuid(cls, v: object) -> str | None:
        return str(v) if v is not None else None
