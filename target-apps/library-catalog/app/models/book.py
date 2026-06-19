import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.sql import text

from app.database import Base
from app.models.pg_types import TimestampTZ


class Book(Base):
    __tablename__ = "books"
    __table_args__ = {"schema": "library_catalog"}

    id = Column(
        PG_UUID(as_uuid=False).with_variant(String(36), "sqlite"),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        server_default=func.gen_random_uuid()
    )
    isbn = Column(String(20), nullable=False, unique=True)
    title = Column(String(500), nullable=False)
    author = Column(String(300), nullable=False)
    total_copies = Column(Integer, nullable=False, default=1)
    created_at = Column(TimestampTZ, nullable=False, default=datetime.utcnow, server_default=func.now())