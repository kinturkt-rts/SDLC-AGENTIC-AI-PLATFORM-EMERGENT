"""Service ORM model."""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.pg_types import TimestampTZ, pg_uuid_column


class Service(Base):
    __tablename__ = "services"

    id: Mapped[str] = mapped_column(pg_uuid_column(), primary_key=True, default=lambda: str(uuid.uuid4()), server_default=func.gen_random_uuid())
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    owner_team: Mapped[str] = mapped_column(String, nullable=False)
    tier: Mapped[str] = mapped_column(String, nullable=False)  # tier1|tier2|tier3
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true", default=True)
    created_at = mapped_column(TimestampTZ, nullable=False, server_default=func.now())
    updated_at = mapped_column(TimestampTZ, nullable=False, server_default=func.now())
