"""StatusHistory ORM model — immutable audit log."""
from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, String, func
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.pg_types import PG_UUID_COL, generate_uuid


class StatusHistory(Base):
    __tablename__ = "status_history"

    id = Column(PG_UUID_COL, primary_key=True, default=generate_uuid, server_default=func.gen_random_uuid())
    work_order_id = Column(PG_UUID_COL, ForeignKey("work_orders.id"), nullable=False)
    actor_user_id = Column(PG_UUID_COL, ForeignKey("users.id"), nullable=False)
    actor_role = Column(String, nullable=False)
    previous_status = Column(String, nullable=True)
    new_status = Column(String, nullable=False)
    context_note = Column(String, nullable=True)
    changed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    work_order = relationship("WorkOrder", back_populates="status_history")
    actor = relationship("User")
