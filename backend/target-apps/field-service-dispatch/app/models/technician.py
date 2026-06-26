"""Technician ORM model."""
from __future__ import annotations

from sqlalchemy import Boolean, Column, String, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy import JSON
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.pg_types import PG_UUID_COL, generate_uuid


class Technician(Base):
    __tablename__ = "technicians"

    id = Column(PG_UUID_COL, primary_key=True, default=generate_uuid, server_default=func.gen_random_uuid())
    display_name = Column(String, nullable=False)
    skills = Column(ARRAY(String).with_variant(JSON(), "sqlite"), nullable=False, server_default="{}")
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")

    user = relationship("User", back_populates="technician", uselist=False)
    work_orders = relationship("WorkOrder", back_populates="assigned_technician")
