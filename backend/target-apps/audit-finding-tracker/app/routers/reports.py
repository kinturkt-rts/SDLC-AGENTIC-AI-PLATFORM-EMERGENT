"""Executive report endpoints."""

from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select, text
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import CurrentUser, require_executive
from app.models.finding import Finding
from app.models.status_history import StatusHistory
from app.models.user import User
from schemas.reports import (
    ExecutiveReportResponse,
    OverdueFinding,
    SeverityDistribution,
    DepartmentSummary
)

router = APIRouter()


@router.get("/executive", response_model=ExecutiveReportResponse)
def get_executive_report(
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    department: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_executive)
):
    """Generate executive dashboard report with overdue findings and metrics."""
    
    # Base query for findings
    base_query = select(Finding)
    
    # Apply date filters if provided
    if start_date:
        base_query = base_query.where(Finding.created_at >= start_date)
    if end_date:
        base_query = base_query.where(Finding.created_at <= end_date)
    
    # TODO: Department filtering - for MVP, we'll skip this as it's not in the schema
    # In production, this would join with a departments table or use a department field
    
    # Get overdue findings
    today = date.today()
    overdue_query = (
        select(Finding)
        .where(Finding.due_date < today)
        .where(Finding.status.notin_(["closed", "verified"]))
    )
    
    overdue_findings_raw = list(db.scalars(overdue_query).all())
    overdue_findings = []
    
    for finding in overdue_findings_raw:
        if finding.due_date:
            days_overdue = (today - finding.due_date).days
            overdue_findings.append(OverdueFinding(
                id=finding.id,
                title=finding.title,
                severity=finding.severity,
                assigned_to=finding.assigned_to,
                due_date=finding.due_date,
                days_overdue=days_overdue
            ))
    
    # Get severity distribution
    severity_query = (
        select(Finding.severity, func.count(Finding.id))
        .group_by(Finding.severity)
    )
    
    severity_results = db.execute(severity_query).fetchall()
    severity_distribution = [
        SeverityDistribution(severity=row[0], count=row[1])
        for row in severity_results
    ]
    
    # Department summaries - simplified for MVP
    # In production, this would be more sophisticated with actual department data
    dept_query = (
        select(
            User.email.label("department"),  # Using email domain as proxy for department
            func.count(Finding.id).label("total_findings"),
            func.sum(
                case((Finding.due_date < today, 1), else_=0)
            ).label("overdue_findings"),
            func.sum(
                case((Finding.status == "closed", 1), else_=0)
            ).label("closed_findings")
        )
        .join(User, Finding.assigned_to == User.id, isouter=True)
        .group_by(User.email)
    )
    
    dept_results = db.execute(dept_query).fetchall()
    department_summaries = []
    
    for row in dept_results:
        dept_name = row.department.split("@")[1] if row.department else "Unassigned"
        department_summaries.append(DepartmentSummary(
            department=dept_name,
            total_findings=row.total_findings or 0,
            overdue_findings=row.overdue_findings or 0,
            closed_findings=row.closed_findings or 0,
            avg_days_to_close=None  # TODO: Calculate from status_history
        ))
    
    # Overall metrics
    total_findings = db.scalar(select(func.count(Finding.id))) or 0
    total_overdue = len(overdue_findings)
    overdue_percentage = (total_overdue / total_findings * 100) if total_findings > 0 else 0
    
    return ExecutiveReportResponse(
        overdue_findings=overdue_findings,
        severity_distribution=severity_distribution,
        department_summaries=department_summaries,
        total_findings=total_findings,
        total_overdue=total_overdue,
        overdue_percentage=round(overdue_percentage, 1)
    )