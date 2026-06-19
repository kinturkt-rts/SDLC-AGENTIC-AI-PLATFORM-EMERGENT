from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, select

from app.dependencies import DbSession, require_librarian_token, get_current_member
from app.models.book import Book
from app.models.loan import Loan
from schemas.book import BookResponse, BookCreate, BookUpdate

router = APIRouter()


def calculate_available_copies(book: Book, db: Session) -> int:
    """Calculate available copies for a book."""
    active_loans = db.scalar(
        select(func.count(Loan.id))
        .where(Loan.book_id == book.id)
        .where(Loan.returned_at.is_(None))
    ) or 0
    return max(0, book.total_copies - active_loans)


@router.get("/", response_model=List[BookResponse])
def search_books(
    db: DbSession,
    query: Optional[str] = Query(None, description="Search books by title or author"),
    available_only: bool = Query(False, description="Only show books with available copies")
):
    """Search books in catalog (anonymous access)."""
    stmt = select(Book)
    
    if query:
        search_term = f"%{query}%"
        stmt = stmt.where(
            (Book.title.ilike(search_term)) | 
            (Book.author.ilike(search_term))
        )
    
    books = list(db.scalars(stmt).all())
    
    result = []
    for book in books:
        available = calculate_available_copies(book, db)
        if available_only and available == 0:
            continue
            
        book_response = BookResponse.model_validate(book)
        book_response.available_copies = available
        result.append(book_response)
    
    return result


@router.post("/", response_model=BookResponse, status_code=201)
def create_book(
    body: BookCreate,
    db: DbSession,
    librarian_token: str = Depends(require_librarian_token)
):
    """Create new book (librarian only)."""
    # Check if ISBN already exists
    existing = db.scalar(select(Book).where(Book.isbn == body.isbn))
    if existing:
        raise HTTPException(status_code=409, detail="Book with this ISBN already exists")
    
    book = Book(**body.model_dump())
    db.add(book)
    db.commit()
    db.refresh(book)
    
    book_response = BookResponse.model_validate(book)
    book_response.available_copies = book.total_copies
    return book_response


@router.patch("/{book_id}", response_model=BookResponse)
def update_book(
    book_id: str,
    body: BookUpdate,
    db: DbSession,
    librarian_token: str = Depends(require_librarian_token)
):
    """Update book details (librarian only)."""
    book = db.scalar(select(Book).where(Book.id == book_id))
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(book, field, value)
    
    db.commit()
    db.refresh(book)
    
    book_response = BookResponse.model_validate(book)
    book_response.available_copies = calculate_available_copies(book, db)
    return book_response


@router.delete("/{book_id}", status_code=204)
def delete_book(
    book_id: str,
    db: DbSession,
    librarian_token: str = Depends(require_librarian_token)
):
    """Delete book if no active loans (librarian only)."""
    book = db.scalar(select(Book).where(Book.id == book_id))
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    # Check for active loans
    active_loans = db.scalar(
        select(func.count(Loan.id))
        .where(Loan.book_id == book_id)
        .where(Loan.returned_at.is_(None))
    ) or 0
    
    if active_loans > 0:
        raise HTTPException(status_code=409, detail="Cannot delete book with active loans")
    
    db.delete(book)
    db.commit()