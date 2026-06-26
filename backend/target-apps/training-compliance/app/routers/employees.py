"""Employees router — CRUD for HR admin."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import CurrentUser
from app.models.entities import AuditLog, Employee
from schemas.employees import EmployeeCreate, EmployeeOut, EmployeeUpdate

router = APIRouter(tags=["employees"])


def _require_hr_admin(current_user: CurrentUser) -> None:
    role = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if role != "hr_admin":
        raise HTTPException(status_code=403, detail="Forbidden")


@router.get("", response_model=list[EmployeeOut])
def list_employees(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[EmployeeOut]:
    """List employees (all authenticated roles)."""
    rows = db.scalars(select(Employee).offset(offset).limit(limit)).all()
    return [EmployeeOut.model_validate(r) for r in rows]


@router.get("/{employee_id}", response_model=EmployeeOut)
def get_employee(
    employee_id: str,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> EmployeeOut:
    """Get a single employee."""
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    return EmployeeOut.model_validate(emp)


@router.post("", response_model=EmployeeOut, status_code=201)
def create_employee(
    body: EmployeeCreate,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> EmployeeOut:
    """Create an employee (HR admin only)."""
    _require_hr_admin(current_user)
    # Check duplicate email
    existing = db.query(Employee).filter(Employee.email == body.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Employee email already exists")
    emp = Employee(
        id=str(uuid.uuid4()),
        full_name=body.full_name,
        email=body.email,
        department_id=body.department_id,
        job_role_id=body.job_role_id,
        manager_id=body.manager_id,
    )
    db.add(emp)
    audit = AuditLog(
        id=str(uuid.uuid4()),
        user_id=str(current_user.id),
        action="CREATE",
        entity="employee",
        entity_id=str(emp.id),
        detail={"full_name": body.full_name},
    )
    db.add(audit)
    db.commit()
    db.refresh(emp)
    return EmployeeOut.model_validate(emp)


@router.patch("/{employee_id}", response_model=EmployeeOut)
def update_employee(
    employee_id: str,
    body: EmployeeUpdate,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> EmployeeOut:
    """Update an employee (HR admin only). PATCH is_active=false to soft-deactivate."""
    _require_hr_admin(current_user)
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    updates = body.model_dump(exclude_unset=True)
    for k, v in updates.items():
        setattr(emp, k, v)
    action = "DEACTIVATE" if updates.get("is_active") is False else "UPDATE"
    audit = AuditLog(
        id=str(uuid.uuid4()),
        user_id=str(current_user.id),
        action=action,
        entity="employee",
        entity_id=str(emp.id),
        detail=updates,
    )
    db.add(audit)
    db.commit()
    db.refresh(emp)
    return EmployeeOut.model_validate(emp)
