"""Auth router — POST /api/v1/auth/token."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.dependencies import DbSession
from app.models.user import User
from app.security import create_access_token, verify_password
from schemas.auth import TokenRequest, TokenResponse

router = APIRouter()


@router.post("/token", response_model=TokenResponse)
def login(body: TokenRequest, db: DbSession) -> TokenResponse:
    user = db.scalars(select(User).where(User.email == body.email)).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token = create_access_token(subject=str(user.id), role=user.role, email=user.email)
    return TokenResponse(access_token=token)
