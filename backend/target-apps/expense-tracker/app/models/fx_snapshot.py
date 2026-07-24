"""FxSnapshot ORM model."""
from __future__ import annotations

import uuid
from datetime import date as date_type
from decimal import Decimal

from sqlalchemy import Date, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.pg_types import pg_uuid_column


class FxSnapshot(Base):
    __tablename__ = "fx_snapshots"
    __table_args__ = (
        UniqueConstraint("currency", "date", name="uq_fx_currency_date"),
    )

    id: Mapped[str] = mapped_column(
        pg_uuid_column(), primary_key=True, default=lambda: str(uuid.uuid4()), server_default=func.gen_random_uuid()
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    date: Mapped[date_type] = mapped_column(Date, nullable=False)
    rate_to_usd: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
