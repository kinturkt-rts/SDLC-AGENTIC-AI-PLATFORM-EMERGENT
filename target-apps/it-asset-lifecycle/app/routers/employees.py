"""Employees router — deactivate endpoint."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.models.employee import Employee
from schemas.employee import EmployeeOut

router = APIRouter(tags=["employees"])


@router.patch("/{employee_id}/deactivate", response_model=EmployeeOut)
def deactivate_employee(
    employee_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("it_admin")),
) -> EmployeeOut:
    """Deactivate an employee — does NOT auto-return active assignments."""
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    if not employee.is_active:
        raise HTTPException(status_code=422, detail="Employee already deactivated")

    employee.is_active = False
    employee.deactivated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(employee)
    return EmployeeOut.model_validate(employee)
