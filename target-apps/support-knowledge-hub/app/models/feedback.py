"""Feedback ORM model."""
from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.pg_types import TimestampTZ, pg_uuid_column


class Feedback(Base):
    __tablename__ = "feedback"
    __table_args__ = (
        UniqueConstraint("search_event_id", "article_id", name="uq_feedback_event_article"),
    )

    id: Mapped[str] = mapped_column(pg_uuid_column(), primary_key=True, default=lambda: __import__('uuid').uuid4().__str__(), server_default=func.gen_random_uuid())
    search_event_id: Mapped[str] = mapped_column(pg_uuid_column(), ForeignKey("search_events.id"), nullable=False)
    article_id: Mapped[str] = mapped_column(pg_uuid_column(), ForeignKey("articles.id"), nullable=False)
    rating: Mapped[str] = mapped_column(String(20), nullable=False)
    timestamp: Mapped[object] = mapped_column(TimestampTZ, nullable=False, server_default=func.now())
