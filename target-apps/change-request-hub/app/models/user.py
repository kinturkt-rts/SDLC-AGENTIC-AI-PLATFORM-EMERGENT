"""User ORM model."""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.pg_types import TimestampTZ, pg_uuid_column


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(pg_uuid_column(), primary_key=True, default=lambda: str(uuid.uuid4()), server_default=func.gen_random_uuid())
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)  # requester|manager|implementer|leadership
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true", default=True)
    created_at = mapped_column(TimestampTZ, nullable=False, server_default=func.now())
