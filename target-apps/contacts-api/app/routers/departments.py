"""Department CRUD routes."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_api_key
from app.models.contact import Contact
from app.models.department import Department
from schemas.department import (
    DepartmentCreate,
    DepartmentDetailOut,
    DepartmentOut,
    DepartmentUpdate,
)

router = APIRouter()


@router.post("/", response_model=DepartmentOut, status_code=201)
def create_department(
    body: DepartmentCreate,
    db: Session = Depends(get_db),
    _api_key: None = Depends(require_api_key),
) -> Department:
    # Check for duplicate code
    existing = db.scalars(
        select(Department).where(Department.code == body.code)
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Department code already exists")

    dept = Department(name=body.name, code=body.code)
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return dept


@router.get("/", response_model=list[DepartmentOut])
def list_departments(db: Session = Depends(get_db)) -> list[Department]:
    return list(db.scalars(select(Department).order_by(Department.name)).all())


@router.get("/{department_id}", response_model=DepartmentDetailOut)
def get_department(
    department_id: str,
    db: Session = Depends(get_db),
) -> dict:
    dept = db.scalars(
        select(Department).where(Department.id == department_id)
    ).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")

    contact_count = db.scalar(
        select(func.count(Contact.id)).where(Contact.department_id == department_id)
    ) or 0

    return {
        "id": dept.id,
        "name": dept.name,
        "code": dept.code,
        "created_at": dept.created_at,
        "contact_count": contact_count,
    }


@router.patch("/{department_id}", response_model=DepartmentOut)
def update_department(
    department_id: str,
    body: DepartmentUpdate,
    db: Session = Depends(get_db),
    _api_key: None = Depends(require_api_key),
) -> Department:
    dept = db.scalars(
        select(Department).where(Department.id == department_id)
    ).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")

    updates = body.model_dump(exclude_unset=True)

    if "code" in updates and updates["code"]:
        conflict = db.scalars(
            select(Department).where(
                Department.code == updates["code"],
                Department.id != department_id,
            )
        ).first()
        if conflict:
            raise HTTPException(status_code=409, detail="Department code already exists")

    for key, value in updates.items():
        setattr(dept, key, value)

    db.commit()
    db.refresh(dept)
    return dept
