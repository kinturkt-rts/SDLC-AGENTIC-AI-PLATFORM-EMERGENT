"""Department ORM model."""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.pg_types import PG_UUID

if TYPE_CHECKING:
    from app.models.contact import Contact


class Department(Base):
    __tablename__ = "departments"
    __table_args__ = {"schema": "contacts_api"}

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False).with_variant(String(36), "sqlite"),
        primary_key=True,
        # Python-side default so tests on SQLite work; Postgres can still override with gen_random_uuid() in DDL.
        default=lambda: str(uuid.uuid4()),
        server_default=func.gen_random_uuid(),
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    code: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, 
        server_default=func.now()
    )

    # Relationships
    contacts: Mapped[list["Contact"]] = relationship(
        "Contact", 
        back_populates="department"
    )