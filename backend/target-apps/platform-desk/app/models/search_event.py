"""SearchEvent model — mirrors platform_desk.search_events."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.pg_types import TimestampTZ, pg_uuid_column


class SearchEvent(Base):
    __tablename__ = "search_events"

    id: Mapped[str] = mapped_column(
        pg_uuid_column(), primary_key=True, default=lambda: str(uuid.uuid4()),
        server_default=func.gen_random_uuid(),
    )
    query_text: Mapped[str] = mapped_column(String(500), nullable=False)
    service_filter_id: Mapped[str | None] = mapped_column(
        pg_uuid_column(), ForeignKey("services.id"), nullable=True,
    )
    result_count: Mapped[int] = mapped_column(Integer, nullable=False)
    top_score: Mapped[float] = mapped_column(Float, nullable=False)
    response_time_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TimestampTZ, nullable=False, server_default=func.now(),
    )
