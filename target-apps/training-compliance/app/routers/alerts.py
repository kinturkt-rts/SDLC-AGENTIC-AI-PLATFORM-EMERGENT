"""Alerts router — overdue, expiring, and data quality flags."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import CurrentUser
from app.models.entities import CompletionRecord, Course, Employee, RoleRequirement
from schemas.compliance import AlertItem

router = APIRouter(tags=["alerts"])


def _get_applicable_course_ids(db: Session, employee: Employee) -> list[str]:
    """Get course IDs applicable to an employee."""
    all_staff_ids = [
        str(c.id) for c in db.scalars(
            select(Course).where(Course.required_for_all_staff == True, Course.is_active == True)  # noqa: E712
        ).all()
    ]
    role_ids = [
        str(r) for r in db.scalars(
            select(RoleRequirement.course_id).where(RoleRequirement.job_role_id == employee.job_role_id)
        ).all()
    ]
    return list(set(all_staff_ids + role_ids))


@router.get("", response_model=list[AlertItem])
def get_alerts(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    type: str | None = Query(default=None, alias="type"),
) -> list[AlertItem]:
    """Get compliance alerts. Manager sees own team only; compliance_officer/hr_admin sees all."""
    role = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if role not in ("manager", "compliance_officer", "hr_admin"):
        raise HTTPException(status_code=403, detail="Forbidden")

    today = date.today()
    soon_cutoff = today + timedelta(days=30)

    # Scope employees
    if role == "manager":
        employees = db.scalars(
            select(Employee).where(
                Employee.manager_id == str(current_user.employee_id),
                Employee.is_active == True,  # noqa: E712
            )
        ).all()
    else:
        employees = db.scalars(
            select(Employee).where(Employee.is_active == True)  # noqa: E712
        ).all()

    alerts: list[AlertItem] = []

    for emp in employees:
        applicable_ids = _get_applicable_course_ids(db, emp)

        for course_id in applicable_ids:
            record = db.query(CompletionRecord).filter(
                CompletionRecord.employee_id == str(emp.id),
                CompletionRecord.course_id == course_id,
                CompletionRecord.is_active_record == True,  # noqa: E712
            ).first()

            if not record or (record.expiry_date and record.expiry_date < today):
                if type is None or type == "overdue":
                    alerts.append(AlertItem(
                        type="overdue",
                        employee_id=str(emp.id),
                        full_name=emp.full_name,
                        detail=f"Course {course_id} is overdue or missing",
                    ))
            elif record.expiry_date and record.expiry_date <= soon_cutoff:
                if type is None or type == "expiring_soon":
                    alerts.append(AlertItem(
                        type="expiring_soon",
                        employee_id=str(emp.id),
                        full_name=emp.full_name,
                        detail=f"Course {course_id} expires {record.expiry_date}",
                    ))

        # Data quality check
        if type is None or type == "data_quality":
            active_count = db.scalar(
                select(func.count(CompletionRecord.id)).where(
                    CompletionRecord.employee_id == str(emp.id),
                    CompletionRecord.is_active_record == True,  # noqa: E712
                )
            ) or 0
            if active_count > 20:
                alerts.append(AlertItem(
                    type="data_quality",
                    employee_id=str(emp.id),
                    full_name=emp.full_name,
                    detail=f"Employee has {active_count} active records (soft cap: 20)",
                ))

    return alerts
