"""Zone ORM model."""
from __future__ import annotations

import datetime
import uuid

from sqlalchemy import CheckConstraint, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.pg_types import pg_uuid_column


class Zone(Base):
    __tablename__ = "zones"
    __table_args__ = (
        CheckConstraint("name IN ('north', 'south', 'lab')", name="zones_name_check"),
        {"schema": "desk_booking"},
    )

    id: Mapped[str] = mapped_column(
        pg_uuid_column(), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
