"""Customer and ServiceAddress ORM models."""
from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, func
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.pg_types import PG_UUID_COL, generate_uuid


class Customer(Base):
    __tablename__ = "customers"

    id = Column(PG_UUID_COL, primary_key=True, default=generate_uuid, server_default=func.gen_random_uuid())
    full_name = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    email = Column(String, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    service_addresses = relationship(
        "ServiceAddress", back_populates="customer", cascade="all, delete-orphan", lazy="joined"
    )
    work_orders = relationship("WorkOrder", back_populates="customer")


class ServiceAddress(Base):
    __tablename__ = "service_addresses"

    id = Column(PG_UUID_COL, primary_key=True, default=generate_uuid, server_default=func.gen_random_uuid())
    customer_id = Column(PG_UUID_COL, ForeignKey("customers.id"), nullable=False)
    street = Column(String, nullable=False)
    city = Column(String, nullable=False)
    state = Column(String, nullable=False)
    postal_code = Column(String, nullable=False)

    customer = relationship("Customer", back_populates="service_addresses")
