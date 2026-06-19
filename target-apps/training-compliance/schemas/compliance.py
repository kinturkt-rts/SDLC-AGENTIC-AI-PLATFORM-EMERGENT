"""Pydantic schemas for compliance views."""
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel


class CourseComplianceStatus(BaseModel):
    course_id: str
    course_name: str
    status: str  # current | expired | missing
    expiry_date: Optional[date] = None


class EmployeeComplianceSummary(BaseModel):
    employee_id: str
    full_name: str
    email: str
    department_id: str
    job_role_id: str
    statuses: list[CourseComplianceStatus]


class DashboardResponse(BaseModel):
    overdue: list[dict]
    expiring_soon: list[dict]
    rate_by_dept: list[dict]
    course_gaps: list[dict]


class AlertItem(BaseModel):
    type: str  # overdue | expiring_soon | data_quality
    employee_id: str
    full_name: str
    detail: Optional[str] = None
