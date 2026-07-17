"""ORM model for faq_collection table."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.pg_types import TimestampTZ


class FaqCollection(Base):
    __tablename__ = "faq_collection"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(TimestampTZ, nullable=False, server_default="now()")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
