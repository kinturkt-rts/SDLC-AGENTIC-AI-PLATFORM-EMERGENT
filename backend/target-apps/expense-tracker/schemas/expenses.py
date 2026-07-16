"""Pydantic schemas for expenses endpoints."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class ExpenseCreate(BaseModel):
    amount: Decimal
    currency: str
    category: str
    description: Optional[str] = None
    expense_date: date

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("amount must be positive")
        return v

    @field_validator("category")
    @classmethod
    def category_valid(cls, v: str) -> str:
        allowed = {"travel", "meals", "software", "other"}
        if v not in allowed:
            raise ValueError(f"category must be one of: {', '.join(sorted(allowed))}")
        return v

    @field_validator("currency")
    @classmethod
    def currency_upper(cls, v: str) -> str:
        return v.upper().strip()


class ExpenseUpdate(BaseModel):
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    expense_date: Optional[date] = None

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v <= 0:
            raise ValueError("amount must be positive")
        return v

    @field_validator("category")
    @classmethod
    def category_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        allowed = {"travel", "meals", "software", "other"}
        if v not in allowed:
            raise ValueError(f"category must be one of: {', '.join(sorted(allowed))}")
        return v

    @field_validator("currency")
    @classmethod
    def currency_upper(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return v.upper().strip()


class ExpenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_id: int
    team_id: int
    original_amount: Decimal
    currency: str
    usd_amount: Decimal
    category: str
    description: Optional[str] = None
    expense_date: date
    status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PagedExpenses(BaseModel):
    items: list[ExpenseOut]
    total: int
    limit: int
    offset: int


class AuditEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    expense_id: int
    from_status: Optional[str] = None
    to_status: str
    actor_id: int
    actor_role: str
    occurred_at: Optional[datetime] = None
