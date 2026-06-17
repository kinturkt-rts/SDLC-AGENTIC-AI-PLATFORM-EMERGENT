"""Auth router — FR-2: `POST /auth/login`."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse
from app.security import create_access_token, verify_password

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
def login(
    payload: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
) -> LoginResponse:
    """Validate credentials and issue a JWT (FR-2).

    Returns 401 for unknown user, wrong password, or `is_active=false`.
    Logs auth failures at WARNING without echoing the password (NFR-8).
    """
    user = db.execute(select(User).where(User.username == payload.username)).scalar_one_or_none()

    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        logger.warning("Login failed for username=%s", payload.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    token, expires_in = create_access_token(subject=str(user.id), role=user.role)
    return LoginResponse(
        access_token=token,
        token_type="bearer",
        role=user.role,
        expires_in=expires_in,
    )
