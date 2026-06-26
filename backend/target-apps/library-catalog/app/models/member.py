import uuid
from datetime import datetime
from sqlalchemy import Column, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.database import Base
from app.models.pg_types import TimestampTZ


class Member(Base):
    __tablename__ = "members"
    __table_args__ = {"schema": "library_catalog"}

    id = Column(
        PG_UUID(as_uuid=False).with_variant(String(36), "sqlite"),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        server_default=func.gen_random_uuid()
    )
    email = Column(String(255), nullable=False, unique=True)
    member_key = Column(String(50), nullable=False, unique=True)
    name = Column(String(200), nullable=False)
    created_at = Column(TimestampTZ, nullable=False, default=datetime.utcnow, server_default=func.now())