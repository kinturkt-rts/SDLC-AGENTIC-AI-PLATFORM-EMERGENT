"""Employees router — team assignment (admin only)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import Actor, require_role
from app.models.employee import Employee
from app.models.team import Team

from schemas.employees import EmployeeTeamUpdate, EmployeeOut

router = APIRouter()


@router.put("/api/v1/employees/{id}/team", response_model=EmployeeOut)
def assign_employee_team(
    id: int,
    body: EmployeeTeamUpdate,
    actor: Actor = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> Employee:
    """FR-7: Assign employee to a team (admin only)."""
    employee = db.scalars(select(Employee).where(Employee.id == id)).first()
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    team = db.scalars(select(Team).where(Team.id == body.team_id, Team.deleted_at.is_(None))).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    employee.team_id = body.team_id
    db.commit()
    db.refresh(employee)
    return employee
