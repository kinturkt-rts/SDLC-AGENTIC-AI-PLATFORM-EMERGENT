"""Auth router — POST /auth/token + GET /auth/token (verify)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import AuthUser
from app.models.user import User
from app.security import create_access_token, verify_password
from schemas.auth import LoginRequest, TokenResponse

router = APIRouter()


@router.post("/auth/token", response_model=TokenResponse)
def login(
    body: LoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Authenticate user and return JWT."""
    user = db.scalars(select(User).where(User.username == body.username)).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is disabled",
        )
    token = create_access_token(subject=str(user.id), role=user.role, username=user.username)
    return TokenResponse(access_token=token, role=user.role)


@router.get("/auth/token")
def verify_token(
    current_user: AuthUser,
) -> dict:
    """Verify current token and return user info."""
    return {
        "user_id": current_user.user_id,
        "username": current_user.username,
        "role": current_user.role,
    }
