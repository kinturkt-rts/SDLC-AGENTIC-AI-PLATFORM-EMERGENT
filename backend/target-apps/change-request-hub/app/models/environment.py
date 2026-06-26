"""Environment ORM model."""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.pg_types import TimestampTZ, pg_uuid_column


class Environment(Base):
    __tablename__ = "environments"

    id: Mapped[str] = mapped_column(pg_uuid_column(), primary_key=True, default=lambda: str(uuid.uuid4()), server_default=func.gen_random_uuid())
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true", default=True)
    created_at = mapped_column(TimestampTZ, nullable=False, server_default=func.now())
