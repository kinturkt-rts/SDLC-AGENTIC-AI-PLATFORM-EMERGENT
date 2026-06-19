"""Pydantic schemas for executive report endpoints."""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional

from pydantic import BaseModel


class ReportParams(BaseModel):
    """Query parameters for executive reports."""
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    department: Optional[str] = None


class OverdueFinding(BaseModel):
    """Overdue finding summary."""
    id: str
    title: str
    severity: str
    assigned_to: Optional[str]
    due_date: date
    days_overdue: int


class SeverityDistribution(BaseModel):
    """Finding count by severity."""
    severity: str
    count: int


class DepartmentSummary(BaseModel):
    """Department-level finding summary."""
    department: str
    total_findings: int
    overdue_findings: int
    closed_findings: int
    avg_days_to_close: Optional[float]


class ExecutiveReportResponse(BaseModel):
    """Executive dashboard report."""
    overdue_findings: List[OverdueFinding]
    severity_distribution: List[SeverityDistribution]
    department_summaries: List[DepartmentSummary]
    total_findings: int
    total_overdue: int
    overdue_percentage: float