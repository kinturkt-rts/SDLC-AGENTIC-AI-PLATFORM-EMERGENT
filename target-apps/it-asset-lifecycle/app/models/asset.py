"""Asset ORM model."""
from __future__ import annotations

import uuid

from sqlalchemy import Column, Date, DateTime, Integer, Numeric, String, func

from app.database import Base
from app.models.pg_types import PGUUID, AssetStatusCol, AssetTypeCol


class Asset(Base):
    __tablename__ = "assets"

    id = Column(PGUUID, primary_key=True, default=lambda: str(uuid.uuid4()), server_default=func.gen_random_uuid())
    asset_type = Column(AssetTypeCol, nullable=False)
    manufacturer = Column(String(200), nullable=False)
    model = Column(String(200), nullable=False)
    serial_number = Column(String(200), nullable=True, unique=True)
    license_key_encrypted = Column(String, nullable=True)
    license_key_last4 = Column(String(4), nullable=True)
    seats_purchased = Column(Integer, nullable=True)
    purchase_date = Column(Date, nullable=False)
    purchase_cost = Column(Numeric(12, 2), nullable=False)
    warranty_end_date = Column(Date, nullable=True)
    status = Column(AssetStatusCol, nullable=False, default="in_stock", server_default="in_stock")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
