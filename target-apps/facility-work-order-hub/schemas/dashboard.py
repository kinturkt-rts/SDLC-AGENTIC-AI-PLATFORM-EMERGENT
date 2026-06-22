"""Dashboard schemas."""
from __future__ import annotations

from pydantic import BaseModel


class SLADashboard(BaseModel):
    open_count: int
    closed_count: int
    overdue_count: int
    avg_days_to_close_by_category: dict[str, float]
    top_sites: list[dict]


class TechnicianWorkload(BaseModel):
    technician_id: str
    display_name: str
    open_count: int
