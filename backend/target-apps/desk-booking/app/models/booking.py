"""Booking ORM model."""
from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Date, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.pg_types import pg_uuid_column, slot_type_enum


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        UniqueConstraint("desk_id", "booking_date", "slot", name="unique_desk_date_slot"),
        {"schema": "desk_booking"},
    )

    id: Mapped[str] = mapped_column(
        pg_uuid_column(), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    desk_id: Mapped[str] = mapped_column(
        pg_uuid_column(), ForeignKey("desk_booking.desks.id"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        pg_uuid_column(), ForeignKey("desk_booking.users.id"), nullable=False
    )
    booking_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    slot: Mapped[str] = mapped_column(slot_type_enum(), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    desk = relationship("Desk", lazy="joined")
    user = relationship("User", lazy="joined")
