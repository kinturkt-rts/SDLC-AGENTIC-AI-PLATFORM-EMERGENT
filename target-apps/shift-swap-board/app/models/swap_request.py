"""ORM model for swap_requests table."""
from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.pg_types import TimestampTZ, pg_enum, pg_uuid_column


class SwapRequest(Base):
    __tablename__ = "swap_requests"

    id: Mapped[str] = mapped_column(
        pg_uuid_column(), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    offered_shift_id: Mapped[str] = mapped_column(
        pg_uuid_column(), ForeignKey("shift_roster.id"), nullable=False
    )
    offered_by_user_id: Mapped[str] = mapped_column(
        pg_uuid_column(), ForeignKey("users.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        pg_enum("swap_status", "open", "claimed", "approved", "denied", "cancelled"),
        nullable=False,
        default="open",
    )
    claimed_by_user_id: Mapped[str | None] = mapped_column(
        pg_uuid_column(), ForeignKey("users.id"), nullable=True
    )
    claimed_at: Mapped[str | None] = mapped_column(TimestampTZ, nullable=True)
    decided_by_user_id: Mapped[str | None] = mapped_column(
        pg_uuid_column(), ForeignKey("users.id"), nullable=True
    )
    decided_at: Mapped[str | None] = mapped_column(TimestampTZ, nullable=True)
    decision_note: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(
        TimestampTZ, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[str] = mapped_column(
        TimestampTZ, server_default=func.now(), nullable=False
    )

    offered_shift: Mapped["ShiftRoster"] = relationship(
        "ShiftRoster", foreign_keys=[offered_shift_id]
    )
    audit_log: Mapped[list["SwapAuditLog"]] = relationship(
        "SwapAuditLog", back_populates="swap_request"
    )
