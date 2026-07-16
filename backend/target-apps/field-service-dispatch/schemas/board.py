"""Board schemas."""
from __future__ import annotations

from pydantic import BaseModel

from schemas.work_order import WorkOrderOut


class BoardWorkOrder(WorkOrderOut):
    """Work order with SLA breach flag."""
    sla_breached: bool = False
    technician_name: str | None = None


class TechnicianColumn(BaseModel):
    technician_id: str
    technician_name: str
    orders: list[BoardWorkOrder]


class BoardResponse(BaseModel):
    unassigned: list[BoardWorkOrder]
    technicians: list[TechnicianColumn]
    sla_breaches: list[BoardWorkOrder]
