from typing import List
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from datetime import datetime, timedelta

from app.dependencies import DbSession, get_current_member
from app.models.loan import Loan
from app.models.book import Book
from app.models.hold import Hold
from app.config import get_settings
from schemas.loan import LoanResponse, LoanCreate

router = APIRouter()


def is_loan_overdue(due_at: datetime) -> bool:
    """Check if a loan is overdue."""
    return due_at < datetime.utcnow() and due_at is not None


@router.post("/", response_model=LoanResponse, status_code=201)
def checkout_book(
    body: LoanCreate,
    db: DbSession,
    current_member = Depends(get_current_member)
):
    """Check out a book (member only)."""
    settings = get_settings()
    
    # Check if book exists
    book = db.scalar(select(Book).where(Book.id == body.book_id))
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    # Check member's active loan count
    active_loans = db.scalar(
        select(func.count(Loan.id))
        .where(Loan.member_id == current_member.id)
        .where(Loan.returned_at.is_(None))
    ) or 0
    
    if active_loans >= settings.max_active_loans:
        raise HTTPException(status_code=409, detail=f"Member has reached maximum of {settings.max_active_loans} active loans")
    
    # Check if member already has this book
    existing_loan = db.scalar(
        select(Loan)
        .where(Loan.book_id == body.book_id)
        .where(Loan.member_id == current_member.id)
        .where(Loan.returned_at.is_(None))
    )
    if existing_loan:
        raise HTTPException(status_code=409, detail="Member already has this book checked out")
    
    # Check availability
    active_book_loans = db.scalar(
        select(func.count(Loan.id))
        .where(Loan.book_id == body.book_id)
        .where(Loan.returned_at.is_(None))
    ) or 0
    
    if active_book_loans >= book.total_copies:
        raise HTTPException(status_code=409, detail="Book is not available for checkout")
    
    # Create loan
    checkout_time = datetime.utcnow()
    due_time = checkout_time + timedelta(days=settings.loan_days)
    
    loan = Loan(
        book_id=body.book_id,
        member_id=current_member.id,
        checkout_at=checkout_time,
        due_at=due_time
    )
    
    db.add(loan)
    db.commit()
    db.refresh(loan)
    
    loan_response = LoanResponse.model_validate(loan)
    loan_response.is_overdue = is_loan_overdue(loan.due_at)
    return loan_response


@router.get("/mine", response_model=List[LoanResponse])
def get_my_loans(
    db: DbSession,
    current_member = Depends(get_current_member)
):
    """Get member's active and recent loans."""
    # Get active loans + 30 most recent returned loans
    stmt = (
        select(Loan)
        .where(Loan.member_id == current_member.id)
        .order_by(Loan.checkout_at.desc())
    )
    
    all_loans = list(db.scalars(stmt).all())
    
    # Separate active and returned loans
    active_loans = [loan for loan in all_loans if loan.returned_at is None]
    returned_loans = [loan for loan in all_loans if loan.returned_at is not None][:30]
    
    result_loans = active_loans + returned_loans
    
    result = []
    for loan in result_loans:
        loan_response = LoanResponse.model_validate(loan)
        loan_response.is_overdue = is_loan_overdue(loan.due_at) if loan.returned_at is None else False
        result.append(loan_response)
    
    return result


@router.put("/{loan_id}/return", response_model=LoanResponse)
def return_book(
    loan_id: str,
    db: DbSession,
    current_member = Depends(get_current_member)
):
    """Return a borrowed book."""
    loan = db.scalar(select(Loan).where(Loan.id == loan_id))
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")
    
    if loan.member_id != current_member.id:
        raise HTTPException(status_code=403, detail="Can only return your own loans")
    
    if loan.returned_at is not None:
        raise HTTPException(status_code=409, detail="Book already returned")
    
    # Mark as returned
    loan.returned_at = datetime.utcnow()
    
    # Auto-fulfill oldest hold for this book
    oldest_hold = db.scalar(
        select(Hold)
        .where(Hold.book_id == loan.book_id)
        .where(Hold.fulfilled_at.is_(None))
        .where(Hold.cancelled_at.is_(None))
        .order_by(Hold.placed_at.asc())
    )
    
    if oldest_hold:
        oldest_hold.fulfilled_at = datetime.utcnow()
        db.add(oldest_hold)
    
    db.commit()
    db.refresh(loan)
    
    loan_response = LoanResponse.model_validate(loan)
    loan_response.is_overdue = False  # Returned loans are not overdue
    return loan_response