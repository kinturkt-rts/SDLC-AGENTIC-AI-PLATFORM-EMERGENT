"""Desk ORM model."""
from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.pg_types import pg_uuid_column


class Desk(Base):
    __tablename__ = "desks"
    __table_args__ = {"schema": "desk_booking"}

    id: Mapped[str] = mapped_column(
        pg_uuid_column(), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    zone_id: Mapped[str] = mapped_column(
        pg_uuid_column(), ForeignKey("desk_booking.zones.id"), nullable=False
    )
    label: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    zone = relationship("Zone", lazy="joined")
