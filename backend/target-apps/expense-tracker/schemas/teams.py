"""Pydantic schemas for teams endpoints."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


class TeamCreate(BaseModel):
    name: str


class TeamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_at: Optional[datetime] = None


class CategoryTotal(BaseModel):
    category: str
    total: Decimal


class ReportOut(BaseModel):
    team_id: int
    year: int
    month: int
    categories: list[CategoryTotal]
    grand_total: Decimal
