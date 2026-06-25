"""Feedback ORM model."""
from __future__ import annotations

import uuid

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.pg_types import pg_uuid_column


class Feedback(Base):
    __tablename__ = "feedback"
    __table_args__ = (
        UniqueConstraint("search_log_id", "article_id", "user_id_hash", name="uq_feedback_dedup"),
    )

    id: Mapped[str] = mapped_column(
        pg_uuid_column(),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        server_default=func.gen_random_uuid(),
    )
    search_log_id: Mapped[str] = mapped_column(
        pg_uuid_column(), ForeignKey("search_logs.id"), nullable=False
    )
    article_id: Mapped[str] = mapped_column(
        pg_uuid_column(), ForeignKey("articles.id"), nullable=False
    )
    user_id_hash: Mapped[str] = mapped_column(String, nullable=False)
    signal: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
