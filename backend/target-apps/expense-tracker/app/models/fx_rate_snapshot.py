"""FX Rate Snapshot ORM model."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import String, Date, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.pg_types import TimestampTZ


class FxRateSnapshot(Base):
    __tablename__ = "fx_rate_snapshots"

    currency: Mapped[str] = mapped_column(String(3), primary_key=True)
    rate_date = mapped_column(Date, primary_key=True)
    usd_rate = mapped_column(Numeric(19, 6), nullable=False)
    loaded_at = mapped_column(TimestampTZ, nullable=True, default=lambda: datetime.now(timezone.utc))
