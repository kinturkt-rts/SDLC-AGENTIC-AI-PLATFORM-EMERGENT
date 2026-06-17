"""Department ORM model."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, String, text

from app.database import Base
from app.models.pg_types import PG_UUID_COL


class Department(Base):
    __tablename__ = "departments"
    __table_args__ = {"schema": "contacts_api"}

    id = Column(PG_UUID_COL, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    code = Column(String, nullable=False, unique=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("CURRENT_TIMESTAMP"),
    )
