"""Review model for PR diff analysis storage."""

import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, CheckConstraint
from sqlalchemy.sql import func

from app.database import Base
from app.models.pg_types import PG_UUID, SAEnum


class RiskBandEnum(str, enum.Enum):
    """Risk band categories for PR analysis."""
    LOW = "low"
    MEDIUM = "medium" 
    HIGH = "high"


class Review(Base):
    """PR diff analysis review record."""
    __tablename__ = "reviews"
    __table_args__ = {"schema": "pr_diff_summarizer"}
    
    id = Column(
        PG_UUID(as_uuid=False).with_variant(String(36), "sqlite"),
        primary_key=True,
        default=lambda: str(__import__("uuid").uuid4()),
        server_default=func.gen_random_uuid()
    )
    submitted_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        server_default=func.current_timestamp()
    )
    title = Column(Text, nullable=False)
    diff_text = Column(Text, nullable=False)
    file_count = Column(Integer, nullable=False, default=0)
    lines_added = Column(Integer, nullable=False, default=0)
    lines_removed = Column(Integer, nullable=False, default=0)
    summary = Column(Text, nullable=False)
    risk_score = Column(
        Integer,
        CheckConstraint("risk_score >= 0 AND risk_score <= 100", name="valid_risk_score"),
        nullable=False,
    )
    risk_band = Column(
        SAEnum(RiskBandEnum, name="risk_band_enum", schema="pr_diff_summarizer", create_type=False, native_enum=True)
        .with_variant(String(10), "sqlite"),
        nullable=False
    )
    model_id = Column(Text, nullable=False)
    created_by = Column(Text, nullable=False)