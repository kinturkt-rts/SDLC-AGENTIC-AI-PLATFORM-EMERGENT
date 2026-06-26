"""Location ORM model."""
from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.pg_types import TimestampTZ, pg_uuid_column


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[str] = mapped_column(pg_uuid_column(), primary_key=True, default=lambda: str(uuid.uuid4()))
    site_id: Mapped[str] = mapped_column(pg_uuid_column(), ForeignKey("sites.id"), nullable=False)
    floor: Mapped[str] = mapped_column(String(64), nullable=False)
    area_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[str] = mapped_column(TimestampTZ, server_default=func.now(), nullable=False)
