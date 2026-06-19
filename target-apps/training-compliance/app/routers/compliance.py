"""Compliance router — per-employee and team compliance views."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import CurrentUser
from app.models.entities import CompletionRecord, Course, Employee, RoleRequirement
from schemas.compliance import CourseComplianceStatus, EmployeeComplianceSummary

router = APIRouter(tags=["compliance"])


def _get_applicable_courses(db: Session, employee: Employee) -> list[Course]:
    """Get all courses applicable to an employee (all-staff + role-specific)."""
    all_staff = db.scalars(
        select(Course).where(Course.required_for_all_staff == True, Course.is_active == True)  # noqa: E712
    ).all()

    role_course_ids = db.scalars(
        select(RoleRequirement.course_id).where(RoleRequirement.job_role_id == employee.job_role_id)
    ).all()
    role_courses = []
    if role_course_ids:
        role_courses = db.scalars(
            select(Course).where(Course.id.in_(role_course_ids), Course.is_active == True)  # noqa: E712
        ).all()

    # Deduplicate by course id
    seen = set()
    result = []
    for c in list(all_staff) + list(role_courses):
        cid = str(c.id)
        if cid not in seen:
            seen.add(cid)
            result.append(c)
    return result


def _compute_compliance(db: Session, employee: Employee) -> list[CourseComplianceStatus]:
    """Compute compliance statuses for an employee."""
    applicable = _get_applicable_courses(db, employee)
    today = date.today()
    statuses = []
    for course in applicable:
        # Find active completion record
        record = db.query(CompletionRecord).filter(
            CompletionRecord.employee_id == str(employee.id),
            CompletionRecord.course_id == str(course.id),
            CompletionRecord.is_active_record == True,  # noqa: E712
        ).first()
        if not record:
            status = "missing"
            expiry = None
        elif record.expiry_date and record.expiry_date < today:
            status = "expired"
            expiry = record.expiry_date
        else:
            status = "current"
            expiry = record.expiry_date
        statuses.append(CourseComplianceStatus(
            course_id=str(course.id),
            course_name=course.name,
            status=status,
            expiry_date=expiry,
        ))
    return statuses


@router.get("/employee/{employee_id}", response_model=list[CourseComplianceStatus])
def get_employee_compliance(
    employee_id: str,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> list[CourseComplianceStatus]:
    """Get compliance status for a specific employee. Scoped by role."""
    role = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)

    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Role scoping
    if role == "employee":
        if str(current_user.employee_id) != employee_id:
            raise HTTPException(status_code=403, detail="Forbidden")
    elif role == "manager":
        if str(employee.manager_id) != str(current_user.employee_id):
            raise HTTPException(status_code=403, detail="Forbidden")
    # hr_admin and compliance_officer can view any

    if not employee.is_active:
        return []

    return _compute_compliance(db, employee)


@router.get("/team", response_model=list[EmployeeComplianceSummary])
def get_team_compliance(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> list[EmployeeComplianceSummary]:
    """Get compliance summary for manager's direct reports only."""
    role = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if role not in ("manager", "hr_admin", "compliance_officer"):
        raise HTTPException(status_code=403, detail="Forbidden")

    if role == "manager":
        team = db.scalars(
            select(Employee).where(
                Employee.manager_id == str(current_user.employee_id),
                Employee.is_active == True,  # noqa: E712
            )
        ).all()
    else:
        # hr_admin and compliance_officer can see all active employees
        team = db.scalars(
            select(Employee).where(Employee.is_active == True)  # noqa: E712
        ).all()

    result = []
    for emp in team:
        statuses = _compute_compliance(db, emp)
        result.append(EmployeeComplianceSummary(
            employee_id=str(emp.id),
            full_name=emp.full_name,
            email=emp.email,
            department_id=str(emp.department_id),
            job_role_id=str(emp.job_role_id),
            statuses=statuses,
        ))
    return result
