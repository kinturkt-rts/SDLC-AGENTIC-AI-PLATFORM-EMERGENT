"""Expense Pydantic schemas."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ExpenseCreate(BaseModel):
    amount: Decimal = Field(..., gt=0)
    currency: str = Field(..., min_length=3, max_length=3)
    category: str = Field(...)
    description: Optional[str] = Field(None, max_length=1000)
    expense_date: date

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        allowed = {"travel", "meals", "software", "other"}
        if v.lower() not in allowed:
            raise ValueError(f"category must be one of: {', '.join(sorted(allowed))}")
        return v.lower()

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, v: str) -> str:
        return v.upper()


class ExpenseUpdate(BaseModel):
    amount: Optional[Decimal] = Field(None, gt=0)
    currency: Optional[str] = Field(None, min_length=3, max_length=3)
    category: Optional[str] = None
    description: Optional[str] = Field(None, max_length=1000)
    expense_date: Optional[date] = None

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str | None) -> str | None:
        if v is None:
            return v
        allowed = {"travel", "meals", "software", "other"}
        if v.lower() not in allowed:
            raise ValueError(f"category must be one of: {', '.join(sorted(allowed))}")
        return v.lower()

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return v.upper()


class ExpenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    team_id: str
    amount: Decimal
    currency: str
    amount_usd: Decimal
    category: str
    description: Optional[str] = None
    expense_date: date
    status: str
    reason: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    @field_validator("id", "user_id", "team_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v: object) -> str | None:
        return str(v) if v is not None else None


class ExpenseListResponse(BaseModel):
    items: list[ExpenseOut]
    total: int
    page: int
    size: int


class StatusChangeRequest(BaseModel):
    reason: Optional[str] = None
