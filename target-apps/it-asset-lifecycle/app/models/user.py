"""User ORM model."""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Column, DateTime, String, func

from app.database import Base
from app.models.pg_types import PGUUID, UserRoleType


class User(Base):
    __tablename__ = "users"

    id = Column(PGUUID, primary_key=True, default=lambda: str(uuid.uuid4()), server_default=func.gen_random_uuid())
    username = Column(String(100), nullable=False, unique=True)
    password_hash = Column(String, nullable=False)
    role = Column(UserRoleType, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
