from fastapi import Header, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import Annotated

from app.config import get_settings
from app.database import get_db


def require_member_key(x_member_key: str | None = Header(default=None, alias="X-Member-Key")) -> str:
    """Validate member key from X-Member-Key header."""
    if not x_member_key:
        raise HTTPException(status_code=401, detail="Invalid or missing member key")
    return x_member_key


def require_librarian_token(x_librarian_token: str | None = Header(default=None, alias="X-Librarian-Token")) -> str:
    """Validate librarian token from X-Librarian-Token header."""
    settings = get_settings()
    if not x_librarian_token or x_librarian_token != settings.librarian_token:
        raise HTTPException(status_code=401, detail="Invalid or missing librarian token")
    return x_librarian_token


def get_current_member(
    member_key: str = Depends(require_member_key),
    db: Session = Depends(get_db)
):
    """Get current member from database by member_key."""
    from app.models.member import Member
    member = db.query(Member).filter(Member.member_key == member_key).first()
    if not member:
        raise HTTPException(status_code=401, detail="Invalid member key")
    return member


# Type aliases for dependency injection
DbSession = Annotated[Session, Depends(get_db)]