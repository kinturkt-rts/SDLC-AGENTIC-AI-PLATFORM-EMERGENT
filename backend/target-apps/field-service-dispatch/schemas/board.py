"""Board and Workload schemas."""
from __future__ import annotations

from pydantic import BaseModel

from schemas.work_order import WorkOrderOut


class BoardResponse(BaseModel):
    unassigned: list[WorkOrderOut]
    technician_columns: dict[str, list[WorkOrderOut]]
    sla_breaches: list[WorkOrderOut]


class TechnicianWorkload(BaseModel):
    technician_id: str
    display_name: str
    total_assigned: int
    in_progress_count: int
    completed_count: int
    sla_breach_flag: bool


class WorkloadResponse(BaseModel):
    workload: list[TechnicianWorkload]
