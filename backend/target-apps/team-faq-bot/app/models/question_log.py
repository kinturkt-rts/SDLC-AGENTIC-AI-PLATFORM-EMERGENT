"""ORM model for question_log table."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.pg_types import TimestampTZ


class QuestionLog(Base):
    __tablename__ = "question_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    logged_at: Mapped[datetime] = mapped_column(TimestampTZ, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(TimestampTZ, nullable=False)
