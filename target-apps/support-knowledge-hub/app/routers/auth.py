"""Authentication router — POST /auth/token."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.dependencies import DbSession
from app.models.user import User
from app.security import create_access_token, verify_password
from schemas.auth import TokenRequest, TokenResponse

router = APIRouter(tags=["auth"])


@router.post("/token", response_model=TokenResponse)
def login(body: TokenRequest, db: DbSession) -> TokenResponse:
    """Issue JWT for valid email/password."""
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token, _ = create_access_token(subject=str(user.id), role=user.role)
    return TokenResponse(access_token=token, role=user.role)
