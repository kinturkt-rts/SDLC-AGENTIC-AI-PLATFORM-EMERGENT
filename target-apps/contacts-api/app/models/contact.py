"""Contact ORM model."""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.pg_types import PG_UUID

if TYPE_CHECKING:
    from app.models.department import Department


class Contact(Base):
    __tablename__ = "contacts"
    __table_args__ = {"schema": "contacts_api"}

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False).with_variant(String(36), "sqlite"),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        server_default=func.gen_random_uuid(),
    )
    department_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False).with_variant(String(36), "sqlite"),
        ForeignKey("contacts_api.departments.id", ondelete="RESTRICT"),
        nullable=False
    )
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    title: Mapped[str | None] = mapped_column(String(80), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, 
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, 
        server_default=func.now(),
        onupdate=func.now()
    )

    # Relationships
    department: Mapped["Department"] = relationship(
        "Department", 
        back_populates="contacts"
    )