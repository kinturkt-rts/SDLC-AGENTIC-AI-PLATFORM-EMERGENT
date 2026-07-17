"""PartLineItem ORM model."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.pg_types import TimestampTZ, pg_uuid_column


class PartLineItem(Base):
    __tablename__ = "part_line_items"

    id: Mapped[str] = mapped_column(
        pg_uuid_column(),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        server_default=func.gen_random_uuid(),
    )
    work_order_id: Mapped[str] = mapped_column(
        pg_uuid_column(), ForeignKey("work_orders.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TimestampTZ, nullable=False, default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    work_order = relationship("WorkOrder", back_populates="parts")
