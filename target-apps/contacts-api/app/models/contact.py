"""Contact ORM model."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, text

from app.database import Base
from app.models.pg_types import PG_UUID_COL


class Contact(Base):
    __tablename__ = "contacts"
    __table_args__ = {"schema": "contacts_api"}

    id = Column(PG_UUID_COL, primary_key=True, default=lambda: str(uuid.uuid4()))
    department_id = Column(
        PG_UUID_COL,
        ForeignKey("contacts_api.departments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    full_name = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True)
    phone = Column(String, nullable=True)
    title = Column(String, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=text("CURRENT_TIMESTAMP"),
    )
