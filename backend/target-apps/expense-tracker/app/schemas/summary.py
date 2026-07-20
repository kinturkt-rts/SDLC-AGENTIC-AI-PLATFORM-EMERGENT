"""Summary Pydantic schemas."""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class CategoryTotal(BaseModel):
    category: str
    total_usd: Decimal


class SummaryOut(BaseModel):
    team_id: str
    year: int
    month: int
    categories: list[CategoryTotal]
    grand_total_usd: Decimal
