"""FAQ router — public read, staff-only create/update."""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_staff
from app.models.faq_entry import FaqEntry
from app.models.user import User
from schemas.faq import FaqCreate, FaqOut, FaqUpdate

router = APIRouter()


@router.get("/", response_model=list[FaqOut])
def list_faqs(
    category: Optional[str] = Query(default=None),
    active: Optional[bool] = Query(default=None),
    db: Session = Depends(get_db),
):
    """List FAQ entries (public). Optional filters: category, active."""
    query = db.query(FaqEntry)
    if category is not None:
        query = query.filter(FaqEntry.category == category)
    if active is not None:
        query = query.filter(FaqEntry.is_active == active)
    return query.order_by(FaqEntry.id).all()


@router.post("/", response_model=FaqOut, status_code=201)
def create_faq(
    body: FaqCreate,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_staff),
):
    """Create a new FAQ entry (staff-only)."""
    faq = FaqEntry(
        category=body.category,
        question=body.question,
        answer=body.answer,
    )
    db.add(faq)
    db.commit()
    db.refresh(faq)
    return faq


@router.put("/{faq_id}", response_model=FaqOut)
def update_faq(
    faq_id: int,
    body: FaqUpdate,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_staff),
):
    """Update an existing FAQ entry (staff-only)."""
    faq = db.query(FaqEntry).filter(FaqEntry.id == faq_id).first()
    if faq is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FAQ entry not found")
    updates = body.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(faq, key, value)
    faq.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(faq)
    return faq
