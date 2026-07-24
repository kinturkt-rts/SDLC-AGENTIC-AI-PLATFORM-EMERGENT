"""Contact CRUD routes."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app.dependencies import DbSession, verify_api_key
from app.models.contact import Contact
from app.models.department import Department
from schemas.contact import ContactCreate, ContactListPage, ContactOut, ContactUpdate

router = APIRouter()


@router.get("", response_model=ContactListPage)
def list_contacts(
    db: DbSession,
    department_id: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    q: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """List contacts with optional filters and pagination. No auth required."""
    # Cap limit at 200
    limit = min(limit, 200)

    base = select(Contact)
    count_base = select(func.count(Contact.id))

    # Filters
    if department_id is not None:
        base = base.where(Contact.department_id == department_id)
        count_base = count_base.where(Contact.department_id == department_id)
    if is_active is not None:
        base = base.where(Contact.is_active == is_active)
        count_base = count_base.where(Contact.is_active == is_active)
    if q:
        pattern = f"%{q}%"
        filter_expr = or_(
            Contact.full_name.ilike(pattern),
            Contact.email.ilike(pattern),
        )
        base = base.where(filter_expr)
        count_base = count_base.where(filter_expr)

    total = db.scalar(count_base) or 0
    rows = db.scalars(base.offset(offset).limit(limit)).all()
    return ContactListPage(items=rows, total=total, limit=limit, offset=offset)


@router.post("", response_model=ContactOut, status_code=status.HTTP_201_CREATED)
def create_contact(
    body: ContactCreate,
    db: DbSession,
    _key: str = Depends(verify_api_key),
):
    """Create a new contact. Requires X-API-Key."""
    # Verify department exists
    dept = db.get(Department, body.department_id)
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found",
        )
    contact = Contact(
        full_name=body.full_name,
        email=body.email,
        department_id=body.department_id,
        phone=body.phone,
        title=body.title,
    )
    db.add(contact)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Contact with email '{body.email}' already exists",
        )
    db.refresh(contact)
    return contact


@router.get("/{contact_id}", response_model=ContactOut)
def get_contact(contact_id: str, db: DbSession):
    """Get a single contact by ID. No auth required."""
    contact = db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found",
        )
    return contact


@router.patch("/{contact_id}", response_model=ContactOut)
def update_contact(
    contact_id: str,
    body: ContactUpdate,
    db: DbSession,
    _key: str = Depends(verify_api_key),
):
    """Partial update of a contact. Requires X-API-Key. Bumps updated_at."""
    contact = db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found",
        )
    updates = body.model_dump(exclude_unset=True)
    # If changing department_id, verify it exists
    if "department_id" in updates:
        dept = db.get(Department, updates["department_id"])
        if not dept:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Department not found",
            )
    for field, value in updates.items():
        setattr(contact, field, value)
    contact.updated_at = datetime.now(timezone.utc)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Contact with email '{updates.get('email', '')}' already exists",
        )
    db.refresh(contact)
    return contact


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_contact(
    contact_id: str,
    db: DbSession,
    _key: str = Depends(verify_api_key),
):
    """Soft-delete a contact (sets is_active=False). Requires X-API-Key."""
    contact = db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found",
        )
    contact.is_active = False
    contact.updated_at = datetime.now(timezone.utc)
    db.commit()
    return None
