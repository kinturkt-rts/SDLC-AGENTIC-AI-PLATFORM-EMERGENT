"""Auth router."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.dependencies import DbSession
from app.models.user import User
from app.security import create_access_token, verify_password
from schemas.auth import LoginRequest, LoginResponse

router = APIRouter(tags=["auth"])


@router.post("/api/v1/auth/login", response_model=LoginResponse)
def login(body: LoginRequest, db: DbSession) -> LoginResponse:
    user = db.scalars(select(User).where(User.email == body.email)).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    token, _ = create_access_token(subject=str(user.id), role=user.role)
    return LoginResponse(access_token=token, role=user.role)
