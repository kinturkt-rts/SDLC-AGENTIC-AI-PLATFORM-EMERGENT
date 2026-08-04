"""Auth router — POST /login. Standard, fixed — do not edit per app.

The route path is fully qualified (/api/v1/auth/login), so register in main.py with NO prefix:
include_router(auth.router, tags=["auth"]). Do not add a prefix or the path will double.
Assumes the standard users table: username (login), password_hash, role.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.dependencies import DbSession
from app.models.user import User
from app.security import create_access_token, verify_password
from schemas.auth import LoginRequest, TokenResponse

router = APIRouter()


@router.post("/api/v1/auth/login", response_model=TokenResponse)
def login(body: LoginRequest, db: DbSession) -> TokenResponse:
    user = db.scalars(select(User).where(User.username == body.username)).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    token, _ = create_access_token(subject=str(user.id), role=user.role)
    return TokenResponse(access_token=token, token_type="bearer")