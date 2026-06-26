from typing import List
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from datetime import datetime

from app.dependencies import DbSession, get_current_member
from app.models.hold import Hold
from app.models.book import Book
from app.models.loan import Loan
from schemas.hold import HoldResponse, HoldCreate

router = APIRouter()


@router.post("/", response_model=HoldResponse, status_code=201)
def place_hold(
    body: HoldCreate,
    db: DbSession,
    current_member = Depends(get_current_member)
):
    """Place hold on unavailable book (member only)."""
    # Check if book exists
    book = db.scalar(select(Book).where(Book.id == body.book_id))
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    # Check if member already has this book
    existing_loan = db.scalar(
        select(Loan)
        .where(Loan.book_id == body.book_id)
        .where(Loan.member_id == current_member.id)
        .where(Loan.returned_at.is_(None))
    )
    if existing_loan:
        raise HTTPException(status_code=409, detail="Cannot place hold on book you currently have")
    
    # Check if member already has an active hold on this book
    existing_hold = db.scalar(
        select(Hold)
        .where(Hold.book_id == body.book_id)
        .where(Hold.member_id == current_member.id)
        .where(Hold.fulfilled_at.is_(None))
        .where(Hold.cancelled_at.is_(None))
    )
    if existing_hold:
        raise HTTPException(status_code=409, detail="Member already has an active hold on this book")
    
    # Check if book is available (optional - can place holds even on available books)
    active_loans = db.scalar(
        select(func.count(Loan.id))
        .where(Loan.book_id == body.book_id)
        .where(Loan.returned_at.is_(None))
    ) or 0
    
    # Create hold
    hold = Hold(
        book_id=body.book_id,
        member_id=current_member.id,
        placed_at=datetime.utcnow()
    )
    
    db.add(hold)
    db.commit()
    db.refresh(hold)
    
    # Calculate queue position
    queue_position = db.scalar(
        select(func.count(Hold.id))
        .where(Hold.book_id == body.book_id)
        .where(Hold.fulfilled_at.is_(None))
        .where(Hold.cancelled_at.is_(None))
        .where(Hold.placed_at <= hold.placed_at)
    ) or 1
    
    hold_response = HoldResponse.model_validate(hold)
    hold_response.queue_position = queue_position
    return hold_response


@router.get("/mine", response_model=List[HoldResponse])
def get_my_holds(
    db: DbSession,
    current_member = Depends(get_current_member)
):
    """Get member's active holds."""
    stmt = (
        select(Hold)
        .where(Hold.member_id == current_member.id)
        .where(Hold.fulfilled_at.is_(None))
        .where(Hold.cancelled_at.is_(None))
        .order_by(Hold.placed_at.desc())
    )
    
    holds = list(db.scalars(stmt).all())
    
    result = []
    for hold in holds:
        # Calculate current queue position
        queue_position = db.scalar(
            select(func.count(Hold.id))
            .where(Hold.book_id == hold.book_id)
            .where(Hold.fulfilled_at.is_(None))
            .where(Hold.cancelled_at.is_(None))
            .where(Hold.placed_at <= hold.placed_at)
        ) or 1
        
        hold_response = HoldResponse.model_validate(hold)
        hold_response.queue_position = queue_position
        result.append(hold_response)
    
    return result


@router.delete("/{hold_id}", status_code=204)
def cancel_hold(
    hold_id: str,
    db: DbSession,
    current_member = Depends(get_current_member)
):
    """Cancel an active hold."""
    hold = db.scalar(select(Hold).where(Hold.id == hold_id))
    if not hold:
        raise HTTPException(status_code=404, detail="Hold not found")
    
    if hold.member_id != current_member.id:
        raise HTTPException(status_code=403, detail="Can only cancel your own holds")
    
    if hold.fulfilled_at is not None:
        raise HTTPException(status_code=409, detail="Cannot cancel fulfilled hold")
    
    if hold.cancelled_at is not None:
        raise HTTPException(status_code=409, detail="Hold already cancelled")
    
    hold.cancelled_at = datetime.utcnow()
    db.commit()