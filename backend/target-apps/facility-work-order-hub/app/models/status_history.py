"""WorkOrderStatusHistory ORM model."""
from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.pg_types import TimestampTZ, pg_enum, pg_uuid_column

wo_status_hist = pg_enum("wo_status_enum", "submitted", "triaged", "assigned", "in_progress", "completed", "closed")


class WorkOrderStatusHistory(Base):
    __tablename__ = "work_order_status_history"

    id: Mapped[str] = mapped_column(pg_uuid_column(), primary_key=True, default=lambda: str(uuid.uuid4()))
    work_order_id: Mapped[str] = mapped_column(pg_uuid_column(), ForeignKey("work_orders.id"), nullable=False)
    from_status: Mapped[str | None] = mapped_column(wo_status_hist, nullable=True)
    to_status: Mapped[str] = mapped_column(wo_status_hist, nullable=False)
    changed_by_user_id: Mapped[str] = mapped_column(pg_uuid_column(), ForeignKey("users.id"), nullable=False)
    changed_at: Mapped[str] = mapped_column(TimestampTZ, server_default=func.now(), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
