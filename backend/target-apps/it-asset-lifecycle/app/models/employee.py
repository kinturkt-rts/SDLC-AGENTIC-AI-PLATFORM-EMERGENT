"""Employee ORM model."""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, func

from app.database import Base
from app.models.pg_types import PGUUID


class Employee(Base):
    __tablename__ = "employees"

    id = Column(PGUUID, primary_key=True, default=lambda: str(uuid.uuid4()), server_default=func.gen_random_uuid())
    full_name = Column(String(200), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    department = Column(String(64), nullable=False)
    manager_id = Column(PGUUID, ForeignKey("employees.id"), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    deactivated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
