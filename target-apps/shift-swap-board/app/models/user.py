"""ORM model for users table."""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.pg_types import TimestampTZ, pg_enum, pg_uuid_column


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        pg_uuid_column(), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(
        pg_enum("user_role", "staff", "floor_lead", "admin"), nullable=False
    )
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[str] = mapped_column(
        TimestampTZ, server_default=func.now(), nullable=False
    )

    staff_profile: Mapped["StaffProfile"] = relationship(
        "StaffProfile", back_populates="user", uselist=False
    )
