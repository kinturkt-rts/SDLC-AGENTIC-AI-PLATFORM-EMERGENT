"""Service model — mirrors platform_desk.services."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.pg_types import TimestampTZ, pg_uuid_column


class Service(Base):
    __tablename__ = "services"

    id: Mapped[str] = mapped_column(
        pg_uuid_column(), primary_key=True, default=lambda: str(uuid.uuid4()),
        server_default=func.gen_random_uuid(),
    )
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    owning_team: Mapped[str] = mapped_column(String, nullable=False)
    criticality_tier: Mapped[int] = mapped_column(Integer, nullable=False)
    active_support: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        TimestampTZ, nullable=False, server_default=func.now(),
    )
