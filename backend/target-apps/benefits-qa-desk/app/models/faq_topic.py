"""FaqTopic ORM model."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.pg_types import TimestampTZ, pg_uuid_column


class FaqTopic(Base):
    __tablename__ = "faq_topics"

    id: Mapped[str] = mapped_column(
        pg_uuid_column(), primary_key=True, default=lambda: str(uuid.uuid4()), server_default=func.gen_random_uuid()
    )
    label: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    created_by: Mapped[str] = mapped_column(pg_uuid_column(), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(TimestampTZ, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(TimestampTZ, nullable=False, server_default=func.now())
