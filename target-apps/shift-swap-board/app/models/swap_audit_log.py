"""ORM model for swap_audit_log table."""
from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.pg_types import TimestampTZ, pg_uuid_column


class SwapAuditLog(Base):
    __tablename__ = "swap_audit_log"

    id: Mapped[str] = mapped_column(
        pg_uuid_column(), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    swap_request_id: Mapped[str] = mapped_column(
        pg_uuid_column(), ForeignKey("swap_requests.id"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_user_id: Mapped[str] = mapped_column(
        pg_uuid_column(), ForeignKey("users.id"), nullable=False
    )
    detail: Mapped[dict | None] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=True
    )
    created_at: Mapped[str] = mapped_column(
        TimestampTZ, server_default=func.now(), nullable=False
    )

    swap_request: Mapped["SwapRequest"] = relationship(
        "SwapRequest", back_populates="audit_log"
    )
