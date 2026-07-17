"""Expense ORM model."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Integer, String, Date, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.pg_types import TimestampTZ


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(Integer, ForeignKey("employees.id"), nullable=False)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), nullable=False)
    original_amount = mapped_column(Numeric(19, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    usd_amount = mapped_column(Numeric(19, 4), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    expense_date = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="submitted")
    created_at = mapped_column(TimestampTZ, nullable=True, default=lambda: datetime.now(timezone.utc))
    updated_at = mapped_column(TimestampTZ, nullable=True)
    deleted_at = mapped_column(TimestampTZ, nullable=True)
