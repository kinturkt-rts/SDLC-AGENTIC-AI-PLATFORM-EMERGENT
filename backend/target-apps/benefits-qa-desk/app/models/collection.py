"""Collection ORM model."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.pg_types import TimestampTZ, pg_uuid_column


class Collection(Base):
    __tablename__ = "collections"

    id: Mapped[str] = mapped_column(
        pg_uuid_column(), primary_key=True, default=lambda: str(uuid.uuid4()), server_default=func.gen_random_uuid()
    )
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(pg_uuid_column(), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(TimestampTZ, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(TimestampTZ, nullable=False, server_default=func.now())

    documents = relationship("Document", back_populates="collection", lazy="select")
