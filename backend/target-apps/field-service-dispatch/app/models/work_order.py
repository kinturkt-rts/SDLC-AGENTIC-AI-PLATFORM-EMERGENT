"""WorkOrder ORM model."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Date, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.pg_types import TimestampTZ, pg_uuid_column


class WorkOrder(Base):
    __tablename__ = "work_orders"

    id: Mapped[str] = mapped_column(
        pg_uuid_column(),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        server_default=func.gen_random_uuid(),
    )
    customer_id: Mapped[str] = mapped_column(
        pg_uuid_column(), ForeignKey("customers.id"), nullable=False
    )
    description: Mapped[str] = mapped_column(String, nullable=False)
    priority: Mapped[str] = mapped_column(String, nullable=False)  # routine / urgent
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False)
    time_window: Mapped[str] = mapped_column(String, nullable=False)  # morning / afternoon / all_day
    status: Mapped[str] = mapped_column(String, nullable=False, default="new", server_default="new")
    completion_notes: Mapped[str | None] = mapped_column(String, nullable=True)
    dispatcher_addendum: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TimestampTZ, nullable=False, default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TimestampTZ, nullable=False, default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    customer = relationship("Customer", back_populates="work_orders")
    assignment = relationship("Assignment", back_populates="work_order", uselist=False)
    parts = relationship("PartLineItem", back_populates="work_order")
    audit_entries = relationship("AuditLog", back_populates="work_order")
