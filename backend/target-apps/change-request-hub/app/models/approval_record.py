"""ApprovalRecord ORM model."""
from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.pg_types import TimestampTZ, pg_uuid_column


class ApprovalRecord(Base):
    __tablename__ = "approval_records"

    id: Mapped[str] = mapped_column(pg_uuid_column(), primary_key=True, default=lambda: str(uuid.uuid4()), server_default=func.gen_random_uuid())
    change_id: Mapped[str] = mapped_column(pg_uuid_column(), ForeignKey("change_requests.id"), nullable=False)
    approver_id: Mapped[str] = mapped_column(pg_uuid_column(), ForeignKey("users.id"), nullable=False)
    decision: Mapped[str] = mapped_column(String, nullable=False)  # approved|rejected
    comment: Mapped[str | None] = mapped_column(String, nullable=True)
    decided_at = mapped_column(TimestampTZ, nullable=False, server_default=func.now())
