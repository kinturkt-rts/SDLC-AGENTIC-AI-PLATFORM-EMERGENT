"""Auth router — POST /auth/login and GET /auth/me."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.dependencies import AuthUser, DbSession
from app.models.user import User
from app.security import create_access_token, verify_password
from schemas.auth import LoginRequest, TokenResponse, UserInfo

router = APIRouter()


@router.post("/auth/login", response_model=TokenResponse)
def login(body: LoginRequest, db: DbSession) -> TokenResponse:
    """Authenticate user and return JWT."""
    user = db.scalars(
        select(User).where(User.username == body.username, User.is_active == True)  # noqa: E712
    ).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    token = create_access_token(subject=str(user.id), role=user.role)
    return TokenResponse(access_token=token)


@router.get("/auth/login")
def login_info() -> dict:
    """Discovery endpoint for login requirements (public)."""
    return {"method": "POST", "fields": ["username", "password"], "token_type": "bearer"}


@router.get("/auth/me", response_model=UserInfo)
def get_me(current_user: AuthUser, db: DbSession) -> UserInfo:
    """Return current user info from JWT."""
    user = db.scalars(select(User).where(User.id == current_user.user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserInfo(
        id=str(user.id),
        username=user.username,
        role=user.role,
        display_name=user.display_name,
    )
