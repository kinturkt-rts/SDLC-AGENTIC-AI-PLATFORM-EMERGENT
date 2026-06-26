"""Assignment ORM model."""
from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, func

from app.database import Base
from app.models.pg_types import PGUUID


class Assignment(Base):
    __tablename__ = "assignments"

    id = Column(PGUUID, primary_key=True, default=lambda: str(uuid.uuid4()), server_default=func.gen_random_uuid())
    asset_id = Column(PGUUID, ForeignKey("assets.id"), nullable=False)
    employee_id = Column(PGUUID, ForeignKey("employees.id"), nullable=False)
    assigned_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    returned_at = Column(DateTime(timezone=True), nullable=True)
    assigned_by = Column(PGUUID, ForeignKey("users.id"), nullable=False)
    return_condition_note = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
