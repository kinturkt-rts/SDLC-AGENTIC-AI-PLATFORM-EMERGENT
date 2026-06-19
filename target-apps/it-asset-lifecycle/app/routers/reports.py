"""Reports router — valuation by department."""
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.models.asset import Asset
from app.models.assignment import Assignment
from app.models.employee import Employee
from schemas.alerts import ValuationByDepartment

router = APIRouter(tags=["reports"])


@router.get("/valuation-by-department", response_model=list[ValuationByDepartment])
def valuation_by_department(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("it_admin", "finance_readonly")),
) -> list[ValuationByDepartment]:
    """Sum of purchase_cost grouped by employee department for active assignments."""
    # Get active assignments joined with assets and employees
    active_assignments = db.execute(
        select(Asset.purchase_cost, Employee.department)
        .join(Assignment, Assignment.asset_id == Asset.id)
        .join(Employee, Employee.id == Assignment.employee_id)
        .where(Assignment.returned_at == None)
    ).all()

    # Group by department
    dept_map: dict[str, dict] = {}
    for row in active_assignments:
        dept = row.department
        cost = Decimal(str(row.purchase_cost)) if row.purchase_cost else Decimal("0")
        if dept not in dept_map:
            dept_map[dept] = {"total_cost": Decimal("0"), "asset_count": 0}
        dept_map[dept]["total_cost"] += cost
        dept_map[dept]["asset_count"] += 1

    return [
        ValuationByDepartment(
            department=dept,
            total_cost=info["total_cost"],
            asset_count=info["asset_count"],
        )
        for dept, info in sorted(dept_map.items())
    ]
