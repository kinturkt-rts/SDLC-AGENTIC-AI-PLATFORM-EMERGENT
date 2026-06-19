"""Contact API routes."""
from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from app.dependencies import ApiKeyAuth, DbSession
from app.models.contact import Contact
from app.models.department import Department
from schemas.contact import ContactCreate, ContactListPage, ContactRead, ContactUpdate

router = APIRouter()


@router.get("/", response_model=ContactListPage)
def list_contacts(
    db: DbSession,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(default=None),
) -> ContactListPage:
    """List contacts with optional search and pagination."""
    query = select(Contact).options(joinedload(Contact.department))
    
    # Apply search filter
    if q:
        search_term = f"%{q}%"
        query = query.where(
            or_(
                Contact.full_name.ilike(search_term),
                Contact.email.ilike(search_term)
            )
        )
    
    # Get total count
    count_query = select(func.count(Contact.id))
    if q:
        search_term = f"%{q}%"
        count_query = count_query.where(
            or_(
                Contact.full_name.ilike(search_term),
                Contact.email.ilike(search_term)
            )
        )
    total = db.scalar(count_query) or 0
    
    # Apply pagination and execute
    contacts = list(db.scalars(query.offset(offset).limit(limit)).all())
    
    return ContactListPage(
        items=contacts,
        total=total,
        limit=limit,
        offset=offset
    )


@router.get("/{id}", response_model=ContactRead)
def get_contact(id: str, db: DbSession) -> Contact:
    """Get a specific contact by ID."""
    contact = db.scalar(
        select(Contact)
        .options(joinedload(Contact.department))
        .where(Contact.id == id)
    )
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found"
        )
    return contact


@router.post("/", response_model=ContactRead, status_code=201)
def create_contact(
    body: ContactCreate,
    db: DbSession,
    _api_key: ApiKeyAuth,
) -> Contact:
    """Create a new contact."""
    # Validate department exists
    department = db.scalar(select(Department).where(Department.id == body.department_id))
    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found"
        )
    
    # Create contact
    contact = Contact(**body.model_dump())
    db.add(contact)
    
    try:
        db.commit()
        db.refresh(contact)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email address already exists"
        )
    
    # Reload with department
    contact = db.scalar(
        select(Contact)
        .options(joinedload(Contact.department))
        .where(Contact.id == contact.id)
    )
    return contact


@router.patch("/{id}", response_model=ContactRead)
def update_contact(
    id: str,
    body: ContactUpdate,
    db: DbSession,
    _api_key: ApiKeyAuth,
) -> Contact:
    """Update an existing contact."""
    contact = db.scalar(select(Contact).where(Contact.id == id))
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found"
        )
    
    updates = body.model_dump(exclude_unset=True)
    
    # Validate department if updating department_id
    if "department_id" in updates:
        department = db.scalar(
            select(Department).where(Department.id == updates["department_id"])
        )
        if not department:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Department not found"
            )
    
    # Apply updates
    for key, value in updates.items():
        setattr(contact, key, value)
    
    try:
        db.commit()
        db.refresh(contact)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email address already exists"
        )
    
    # Reload with department
    contact = db.scalar(
        select(Contact)
        .options(joinedload(Contact.department))
        .where(Contact.id == contact.id)
    )
    return contact


@router.delete("/{id}", status_code=204, response_model=None)
def delete_contact(
    id: str,
    db: DbSession,
    _api_key: ApiKeyAuth,
) -> None:
    """Soft delete a contact (set is_active=false)."""
    contact = db.scalar(select(Contact).where(Contact.id == id))
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found"
        )
    
    contact.is_active = False
    db.commit()