"""Assignment ORM model."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.pg_types import TimestampTZ, pg_uuid_column


class Assignment(Base):
    __tablename__ = "assignments"

    id: Mapped[str] = mapped_column(
        pg_uuid_column(),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        server_default=func.gen_random_uuid(),
    )
    work_order_id: Mapped[str] = mapped_column(
        pg_uuid_column(), ForeignKey("work_orders.id"), nullable=False
    )
    technician_id: Mapped[str] = mapped_column(
        pg_uuid_column(), ForeignKey("technicians.id"), nullable=False
    )
    assigned_by: Mapped[str] = mapped_column(
        pg_uuid_column(), ForeignKey("users.id"), nullable=False
    )
    assigned_at: Mapped[datetime] = mapped_column(
        TimestampTZ, nullable=False, default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    work_order = relationship("WorkOrder", back_populates="assignment")
    technician = relationship("Technician", back_populates="assignments")
