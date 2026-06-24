"""ORM model for shift_roster table."""
from __future__ import annotations

import uuid

from sqlalchemy import Date, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.pg_types import TimestampTZ, pg_enum, pg_uuid_column


class ShiftRoster(Base):
    __tablename__ = "shift_roster"
    __table_args__ = (
        UniqueConstraint("staff_id", "shift_date", "shift_window", name="uq_staff_date_window"),
    )

    id: Mapped[str] = mapped_column(
        pg_uuid_column(), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    staff_id: Mapped[str] = mapped_column(
        pg_uuid_column(), ForeignKey("staff_profiles.id"), nullable=False
    )
    shift_date: Mapped[str] = mapped_column(Date, nullable=False)
    shift_window: Mapped[str] = mapped_column(
        pg_enum("shift_window", "morning", "afternoon", "full"), nullable=False
    )
    created_at: Mapped[str] = mapped_column(
        TimestampTZ, server_default=func.now(), nullable=False
    )

    staff_profile: Mapped["StaffProfile"] = relationship(
        "StaffProfile", back_populates="shifts"
    )
