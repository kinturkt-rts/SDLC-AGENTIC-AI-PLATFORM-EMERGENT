"""Blackout ORM model."""
from __future__ import annotations

import datetime
import uuid

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.pg_types import pg_uuid_column


class Blackout(Base):
    __tablename__ = "blackouts"
    __table_args__ = (
        CheckConstraint("starts_on <= ends_on", name="blackouts_date_range_check"),
        {"schema": "desk_booking"},
    )

    id: Mapped[str] = mapped_column(
        pg_uuid_column(), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    desk_id: Mapped[str] = mapped_column(
        pg_uuid_column(), ForeignKey("desk_booking.desks.id"), nullable=False
    )
    starts_on: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    desk = relationship("Desk", lazy="joined")
