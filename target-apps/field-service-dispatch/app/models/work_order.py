"""WorkOrder and WorkOrderPart ORM models."""
from __future__ import annotations

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.pg_types import PG_UUID_COL, generate_uuid


class WorkOrder(Base):
    __tablename__ = "work_orders"

    id = Column(PG_UUID_COL, primary_key=True, default=generate_uuid, server_default=func.gen_random_uuid())
    customer_id = Column(PG_UUID_COL, ForeignKey("customers.id"), nullable=False)
    description = Column(String, nullable=False)
    priority = Column(String, nullable=False)  # routine, urgent
    scheduled_date = Column(Date, nullable=False)
    time_window = Column(String, nullable=False)  # morning, afternoon, all_day
    status = Column(String, nullable=False, default="new", server_default="new")
    assigned_technician_id = Column(PG_UUID_COL, ForeignKey("technicians.id"), nullable=True)
    completion_notes = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    customer = relationship("Customer", back_populates="work_orders")
    assigned_technician = relationship("Technician", back_populates="work_orders")
    parts = relationship("WorkOrderPart", back_populates="work_order", cascade="all, delete-orphan", lazy="joined")
    status_history = relationship("StatusHistory", back_populates="work_order", order_by="StatusHistory.changed_at")


class WorkOrderPart(Base):
    __tablename__ = "work_order_parts"

    id = Column(PG_UUID_COL, primary_key=True, default=generate_uuid, server_default=func.gen_random_uuid())
    work_order_id = Column(PG_UUID_COL, ForeignKey("work_orders.id"), nullable=False)
    part_name = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_cost = Column(Numeric(10, 2), nullable=True)

    work_order = relationship("WorkOrder", back_populates="parts")
