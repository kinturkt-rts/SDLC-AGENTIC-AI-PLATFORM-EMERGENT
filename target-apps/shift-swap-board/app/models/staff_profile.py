"""ORM model for staff_profiles table."""
from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.pg_types import pg_uuid_column


class StaffProfile(Base):
    __tablename__ = "staff_profiles"

    id: Mapped[str] = mapped_column(
        pg_uuid_column(), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        pg_uuid_column(), ForeignKey("users.id"), unique=True, nullable=False
    )
    employee_code: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="staff_profile")
    shifts: Mapped[list["ShiftRoster"]] = relationship(
        "ShiftRoster", back_populates="staff_profile"
    )
