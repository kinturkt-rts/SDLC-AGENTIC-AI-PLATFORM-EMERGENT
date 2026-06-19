"""User ORM model."""
from __future__ import annotations

from sqlalchemy import Column, ForeignKey, String, func
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.pg_types import PG_UUID_COL, generate_uuid


class User(Base):
    __tablename__ = "users"

    id = Column(PG_UUID_COL, primary_key=True, default=generate_uuid, server_default=func.gen_random_uuid())
    username = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False)  # dispatcher, technician, owner
    technician_id = Column(PG_UUID_COL, ForeignKey("technicians.id"), nullable=True)

    technician = relationship("Technician", back_populates="user", uselist=False, foreign_keys=[technician_id])
