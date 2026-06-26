"""StockMovement ORM model — mirrors `inventory_app.stock_movements` (DDL 004).

Immutable audit trail per design §5: never updated or deleted via API. Cascade
delete only fires when a parent product is removed (FR-11).
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.schema import orm_table_args


class MovementReason(str, enum.Enum):
    """Mirrors Postgres `inventory_app.movement_reason` enum."""

    sale = "sale"
    restock = "restock"
    adjustment = "adjustment"


class StockMovement(Base):
    __tablename__ = "stock_movements"
    __table_args__ = orm_table_args()

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True).with_variant(String(36), "sqlite"),
        primary_key=True,
        default=uuid.uuid4,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True).with_variant(String(36), "sqlite"),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(16), nullable=False)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    performed_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True).with_variant(String(36), "sqlite"),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    product = relationship("Product", back_populates="movements")
