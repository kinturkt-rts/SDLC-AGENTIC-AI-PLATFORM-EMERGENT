"""SearchLog ORM model."""
from __future__ import annotations

import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.pg_types import pg_uuid_column


class SearchLog(Base):
    __tablename__ = "search_logs"

    id: Mapped[str] = mapped_column(
        pg_uuid_column(),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        server_default=func.gen_random_uuid(),
    )
    user_id_hash: Mapped[str] = mapped_column(String, nullable=False)
    query_text: Mapped[str] = mapped_column(String, nullable=False)
    category_filter: Mapped[str | None] = mapped_column(
        pg_uuid_column(), ForeignKey("categories.id"), nullable=True
    )
    result_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    executed_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
