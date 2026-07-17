"""Auth router."""
from __future__ import annotations

import secrets

from fastapi import APIRouter, HTTPException, status

from app.dependencies import DbSession
from app.models.user import User
from app.security import verify_password
from schemas.auth import TokenRequest, TokenResponse

router = APIRouter()


@router.post("/api/v1/auth/token", response_model=TokenResponse)
def create_token(body: TokenRequest, db: DbSession) -> TokenResponse:
    """Authenticate user and return an API key token."""
    user = db.query(User).filter(User.username == body.username).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    if not user.api_key:
        user.api_key = secrets.token_urlsafe(32)
        db.commit()
        db.refresh(user)
    return TokenResponse(
        access_token=user.api_key,
        role=user.role,
        technician_id=str(user.technician_id) if user.technician_id else None,
    )
