from sqlalchemy import Column, Integer, JSON, String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB

from app.database import Base
from app.models.pg_types import TimestampTZ


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = {"schema": "library_catalog"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(PG_UUID(as_uuid=False).with_variant(String(36), "sqlite"), nullable=False)
    action = Column(String(50), nullable=False)
    member_id = Column(
        PG_UUID(as_uuid=False).with_variant(String(36), "sqlite"),
        ForeignKey("library_catalog.members.id", ondelete="SET NULL"),
        nullable=True
    )
    timestamp = Column(TimestampTZ, nullable=False)
    details = Column(JSONB().with_variant(JSON(), "sqlite"), nullable=True)