"""Department CRUD routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.dependencies import DbSession, verify_api_key
from app.models.contact import Contact
from app.models.department import Department
from schemas.department import (
    DepartmentCreate,
    DepartmentDetail,
    DepartmentOut,
    DepartmentUpdate,
)

router = APIRouter()


@router.get("", response_model=list[DepartmentOut])
def list_departments(db: DbSession):
    """Return all departments sorted alphabetically by name. No auth required."""
    stmt = select(Department).order_by(Department.name.asc())
    rows = db.scalars(stmt).all()
    return rows


@router.post("", response_model=DepartmentOut, status_code=status.HTTP_201_CREATED)
def create_department(
    body: DepartmentCreate,
    db: DbSession,
    _key: str = Depends(verify_api_key),
):
    """Create a new department. Requires X-API-Key."""
    dept = Department(name=body.name, code=body.code)
    db.add(dept)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Department with code '{body.code}' already exists",
        )
    db.refresh(dept)
    return dept


@router.get("/{department_id}", response_model=DepartmentDetail)
def get_department(department_id: str, db: DbSession):
    """Get a single department with contact_count. No auth required."""
    dept = db.get(Department, department_id)
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found",
        )
    # Count contacts (active + inactive)
    count_stmt = select(func.count(Contact.id)).where(
        Contact.department_id == department_id
    )
    contact_count = db.scalar(count_stmt) or 0
    return DepartmentDetail(
        id=str(dept.id),
        name=dept.name,
        code=dept.code,
        created_at=dept.created_at,
        contact_count=contact_count,
    )


@router.patch("/{department_id}", response_model=DepartmentOut)
def update_department(
    department_id: str,
    body: DepartmentUpdate,
    db: DbSession,
    _key: str = Depends(verify_api_key),
):
    """Partial update of a department. Requires X-API-Key."""
    dept = db.get(Department, department_id)
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found",
        )
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(dept, field, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Department with code '{updates.get('code', '')}' already exists",
        )
    db.refresh(dept)
    return dept
