import secrets
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select

from app.dependencies import DbSession, require_librarian_token
from app.models.member import Member
from schemas.member import MemberResponse, MemberCreate

router = APIRouter()


def generate_member_key() -> str:
    """Generate a secure member key."""
    return f"MBR_{secrets.token_urlsafe(16)}"


@router.post("/", response_model=MemberResponse, status_code=201)
def create_member(
    body: MemberCreate,
    db: DbSession,
    librarian_token: str = Depends(require_librarian_token)
):
    """Create new member (librarian only)."""
    # Check if email already exists
    existing = db.scalar(select(Member).where(Member.email == body.email))
    if existing:
        raise HTTPException(status_code=409, detail="Member with this email already exists")
    
    # Generate unique member key
    member_key = generate_member_key()
    while db.scalar(select(Member).where(Member.member_key == member_key)):
        member_key = generate_member_key()
    
    member = Member(
        email=body.email,
        name=body.name,
        member_key=member_key
    )
    
    db.add(member)
    db.commit()
    db.refresh(member)
    
    return MemberResponse.model_validate(member)