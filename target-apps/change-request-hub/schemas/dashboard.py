"""Dashboard schemas."""
from __future__ import annotations

from pydantic import BaseModel


class DashboardSummary(BaseModel):
    counts_by_status: dict[str, int]
    counts_by_risk: dict[str, int]
    overdue_scheduled_count: int
    monthly_by_env: list[dict]
    top_services: list[dict]
    active_emergency_count: int
