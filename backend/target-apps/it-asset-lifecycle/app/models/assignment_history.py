"""AssignmentHistory ORM model — append-only audit log."""
from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, func

from app.database import Base
from app.models.pg_types import PGUUID, AssignmentEventTypeCol


class AssignmentHistory(Base):
    __tablename__ = "assignment_history"

    id = Column(PGUUID, primary_key=True, default=lambda: str(uuid.uuid4()), server_default=func.gen_random_uuid())
    asset_id = Column(PGUUID, ForeignKey("assets.id"), nullable=False)
    employee_id = Column(PGUUID, ForeignKey("employees.id"), nullable=False)
    event_type = Column(AssignmentEventTypeCol, nullable=False)
    event_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    actor_id = Column(PGUUID, ForeignKey("users.id"), nullable=False)
    condition_note = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
