"""Site ORM model."""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.pg_types import TimestampTZ, pg_uuid_column


class Site(Base):
    __tablename__ = "sites"

    id: Mapped[str] = mapped_column(pg_uuid_column(), primary_key=True, default=lambda: str(uuid.uuid4()))
    site_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address_line: Mapped[str] = mapped_column(String(512), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[str] = mapped_column(TimestampTZ, server_default=func.now(), nullable=False)
    updated_at: Mapped[str] = mapped_column(TimestampTZ, server_default=func.now(), onupdate=func.now(), nullable=False)
