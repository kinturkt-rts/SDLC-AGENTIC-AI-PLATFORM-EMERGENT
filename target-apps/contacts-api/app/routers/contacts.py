"""Contact CRUD routes with filtering, search, and pagination."""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_api_key
from app.models.contact import Contact
from app.models.department import Department
from schemas.contact import ContactCreate, ContactListPage, ContactOut, ContactUpdate

router = APIRouter()


@router.post("/", response_model=ContactOut, status_code=201)
def create_contact(
    body: ContactCreate,
    db: Session = Depends(get_db),
    _api_key: None = Depends(require_api_key),
) -> Contact:
    # Validate department exists
    dept = db.scalars(
        select(Department).where(Department.id == body.department_id)
    ).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")

    # Check duplicate email
    existing = db.scalars(
        select(Contact).where(Contact.email == body.email)
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already exists")

    contact = Contact(
        full_name=body.full_name,
        email=body.email,
        department_id=body.department_id,
        phone=body.phone,
        title=body.title,
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


@router.get("/", response_model=ContactListPage)
def list_contacts(
    q: Optional[str] = Query(default=None),
    department_id: Optional[str] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(Contact)
    count_stmt = select(func.count(Contact.id))

    # Filter: department_id
    if department_id is not None:
        stmt = stmt.where(Contact.department_id == department_id)
        count_stmt = count_stmt.where(Contact.department_id == department_id)

    # Filter: is_active
    if is_active is not None:
        stmt = stmt.where(Contact.is_active == is_active)
        count_stmt = count_stmt.where(Contact.is_active == is_active)

    # Search: case-insensitive partial match on full_name or email
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(
            Contact.full_name.ilike(pattern) | Contact.email.ilike(pattern)
        )
        count_stmt = count_stmt.where(
            Contact.full_name.ilike(pattern) | Contact.email.ilike(pattern)
        )

    total = db.scalar(count_stmt) or 0
    rows = list(db.scalars(stmt.offset(offset).limit(limit)).all())

    return {"items": rows, "total": total, "limit": limit, "offset": offset}


@router.get("/{contact_id}", response_model=ContactOut)
def get_contact(
    contact_id: str,
    db: Session = Depends(get_db),
) -> Contact:
    contact = db.scalars(
        select(Contact).where(Contact.id == contact_id)
    ).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact


@router.patch("/{contact_id}", response_model=ContactOut)
def update_contact(
    contact_id: str,
    body: ContactUpdate,
    db: Session = Depends(get_db),
    _api_key: None = Depends(require_api_key),
) -> Contact:
    contact = db.scalars(
        select(Contact).where(Contact.id == contact_id)
    ).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    updates = body.model_dump(exclude_unset=True)

    # If email is being changed, check uniqueness
    if "email" in updates and updates["email"]:
        conflict = db.scalars(
            select(Contact).where(
                Contact.email == updates["email"],
                Contact.id != contact_id,
            )
        ).first()
        if conflict:
            raise HTTPException(status_code=409, detail="Email already exists")

    # If department_id is being changed, validate it exists
    if "department_id" in updates and updates["department_id"]:
        dept = db.scalars(
            select(Department).where(Department.id == updates["department_id"])
        ).first()
        if not dept:
            raise HTTPException(status_code=404, detail="Department not found")

    for key, value in updates.items():
        setattr(contact, key, value)

    # Manually bump updated_at for SQLite (onupdate doesn't fire on setattr alone)
    contact.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(contact)
    return contact


@router.delete("/{contact_id}", status_code=204, response_model=None)
def delete_contact(
    contact_id: str,
    db: Session = Depends(get_db),
    _api_key: None = Depends(require_api_key),
) -> None:
    contact = db.scalars(
        select(Contact).where(Contact.id == contact_id)
    ).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    # Soft-delete: flip is_active to False
    contact.is_active = False
    contact.updated_at = datetime.now(timezone.utc)
    db.commit()
