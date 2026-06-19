"""Department API routes."""
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import ApiKeyAuth, DbSession
from app.models.department import Department
from schemas.department import DepartmentCreate, DepartmentRead, DepartmentUpdate

router = APIRouter()


@router.get("/", response_model=list[DepartmentRead])
def list_departments(db: DbSession) -> list[Department]:
    """List all departments."""
    departments = list(db.scalars(select(Department)).all())
    return departments


@router.post("/", response_model=DepartmentRead, status_code=201)
def create_department(
    body: DepartmentCreate,
    db: DbSession,
    _api_key: ApiKeyAuth,
) -> Department:
    """Create a new department."""
    # Check for duplicate code
    existing = db.scalar(select(Department).where(Department.code == body.code))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Department code '{body.code}' already exists"
        )
    
    department = Department(**body.model_dump())
    db.add(department)
    db.commit()
    db.refresh(department)
    return department


@router.patch("/{id}", response_model=DepartmentRead)
def update_department(
    id: str,
    body: DepartmentUpdate,
    db: DbSession,
    _api_key: ApiKeyAuth,
) -> Department:
    """Update an existing department."""
    department = db.scalar(select(Department).where(Department.id == id))
    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found"
        )
    
    updates = body.model_dump(exclude_unset=True)
    
    # Check for duplicate code if updating code
    if "code" in updates:
        existing = db.scalar(
            select(Department).where(
                Department.code == updates["code"],
                Department.id != id
            )
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Department code '{updates['code']}' already exists"
            )
    
    for key, value in updates.items():
        setattr(department, key, value)
    
    db.commit()
    db.refresh(department)
    return department