"""Reports/dashboard router — compliance officer org-wide views."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import CurrentUser
from app.models.entities import CompletionRecord, Course, Department, Employee, RoleRequirement
from schemas.compliance import DashboardResponse

router = APIRouter(tags=["reports"])


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


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> DashboardResponse:
    """Org-wide compliance dashboard (compliance officer only)."""
    role = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if role not in ("compliance_officer", "hr_admin"):
        raise HTTPException(status_code=403, detail="Forbidden")

    today = date.today()
    soon_cutoff = today + timedelta(days=30)
    active_employees = db.scalars(
        select(Employee).where(Employee.is_active == True)  # noqa: E712
    ).all()

    overdue_list = []
    expiring_soon_list = []
    dept_stats: dict[str, dict] = {}  # dept_id -> {total, compliant}
    course_gaps: dict[str, int] = {}  # course_id -> gap count

    # Get departments for name lookup
    departments = {str(d.id): d.name for d in db.scalars(select(Department)).all()}
    courses_map = {str(c.id): c.name for c in db.scalars(select(Course)).all()}

    for emp in active_employees:
        dept_id = str(emp.department_id)
        if dept_id not in dept_stats:
            dept_stats[dept_id] = {"total": 0, "compliant": 0}
        dept_stats[dept_id]["total"] += 1

        applicable_ids = _get_applicable_course_ids(db, emp)
        has_gap = False
        has_expiring = False

        for course_id in applicable_ids:
            record = db.query(CompletionRecord).filter(
                CompletionRecord.employee_id == str(emp.id),
                CompletionRecord.course_id == course_id,
                CompletionRecord.is_active_record == True,  # noqa: E712
            ).first()

            if not record:
                has_gap = True
                course_gaps[course_id] = course_gaps.get(course_id, 0) + 1
            elif record.expiry_date and record.expiry_date < today:
                has_gap = True
                course_gaps[course_id] = course_gaps.get(course_id, 0) + 1
            elif record.expiry_date and record.expiry_date <= soon_cutoff:
                has_expiring = True

        if has_gap:
            overdue_list.append({
                "employee_id": str(emp.id),
                "full_name": emp.full_name,
                "email": emp.email,
            })
        elif has_expiring:
            expiring_soon_list.append({
                "employee_id": str(emp.id),
                "full_name": emp.full_name,
                "email": emp.email,
            })

        if not has_gap:
            dept_stats[dept_id]["compliant"] += 1

    # Build rate_by_dept
    rate_by_dept = []
    for dept_id, stats in dept_stats.items():
        rate = (stats["compliant"] / stats["total"] * 100) if stats["total"] > 0 else 0.0
        rate_by_dept.append({
            "department_id": dept_id,
            "department_name": departments.get(dept_id, "Unknown"),
            "total": stats["total"],
            "compliant": stats["compliant"],
            "rate": round(rate, 1),
        })

    # Build course_gaps sorted desc
    course_gaps_list = sorted(
        [{"course_id": cid, "course_name": courses_map.get(cid, "Unknown"), "gap_count": count}
         for cid, count in course_gaps.items()],
        key=lambda x: x["gap_count"],
        reverse=True,
    )

    return DashboardResponse(
        overdue=overdue_list,
        expiring_soon=expiring_soon_list,
        rate_by_dept=rate_by_dept,
        course_gaps=course_gaps_list,
    )
