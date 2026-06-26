"""RunbookStep model — mirrors platform_desk.runbook_steps."""
from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.pg_types import pg_uuid_column


class RunbookStep(Base):
    __tablename__ = "runbook_steps"

    id: Mapped[str] = mapped_column(
        pg_uuid_column(), primary_key=True, default=lambda: str(uuid.uuid4()),
        server_default=func.gen_random_uuid(),
    )
    runbook_id: Mapped[str] = mapped_column(
        pg_uuid_column(), ForeignKey("runbooks.id"), nullable=False,
    )
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    body_text: Mapped[str] = mapped_column(String, nullable=False)
    estimated_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    warning_callout: Mapped[str | None] = mapped_column(String, nullable=True)

    runbook = relationship("Runbook", back_populates="steps")
