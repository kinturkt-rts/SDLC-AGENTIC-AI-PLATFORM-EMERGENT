"""API key model for authentication."""

from datetime import datetime
from sqlalchemy import Column, String, Text, Boolean, DateTime
from sqlalchemy.sql import func

from app.database import Base


class ApiKey(Base):
    """API key authentication record."""
    __tablename__ = "api_keys"
    __table_args__ = {"schema": "pr_diff_summarizer"}
    
    key_hash = Column(String(255), primary_key=True)
    name = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        server_default=func.current_timestamp()
    )
    is_active = Column(Boolean, nullable=False, default=True)