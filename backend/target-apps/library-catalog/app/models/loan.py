import uuid
from datetime import datetime
from sqlalchemy import Column, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship
from sqlalchemy import String

from app.database import Base
from app.models.pg_types import TimestampTZ


class Loan(Base):
    __tablename__ = "loans"
    __table_args__ = {"schema": "library_catalog"}

    id = Column(
        PG_UUID(as_uuid=False).with_variant(String(36), "sqlite"),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        server_default=func.gen_random_uuid()
    )
    book_id = Column(
        PG_UUID(as_uuid=False).with_variant(String(36), "sqlite"),
        ForeignKey("library_catalog.books.id", ondelete="RESTRICT"),
        nullable=False
    )
    member_id = Column(
        PG_UUID(as_uuid=False).with_variant(String(36), "sqlite"),
        ForeignKey("library_catalog.members.id", ondelete="RESTRICT"),
        nullable=False
    )
    checkout_at = Column(TimestampTZ, nullable=False, default=datetime.utcnow, server_default=func.now())
    due_at = Column(TimestampTZ, nullable=False)
    returned_at = Column(TimestampTZ, nullable=True)

    # Relationships
    book = relationship("Book", lazy="select")
    member = relationship("Member", lazy="select")