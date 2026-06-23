"""Auth router — POST /api/v1/auth/token."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.dependencies import DbSession
from app.models.user import User
from app.security import create_access_token, verify_password
from schemas.auth import TokenRequest, TokenResponse

router = APIRouter()


@router.post("/api/v1/auth/token", response_model=TokenResponse)
def login(body: TokenRequest, db: DbSession) -> TokenResponse:
    """Authenticate and return a JWT."""
    user = db.scalars(select(User).where(User.email == body.email, User.active == True)).first()  # noqa: E712
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token, _ = create_access_token(subject=str(user.id), role=user.role)
    return TokenResponse(access_token=token, token_type="bearer")
