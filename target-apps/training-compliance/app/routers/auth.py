"""Auth router — POST /auth/token issues JWT."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.entities import User
from app.security import create_access_token, verify_password
from schemas.auth import TokenRequest, TokenResponse

router = APIRouter(tags=["auth"])


@router.post("/token", response_model=TokenResponse)
def login(body: TokenRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Authenticate user and return JWT access token."""
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token, _ = create_access_token(
        subject=str(user.id),
        role=str(user.role.value) if hasattr(user.role, "value") else str(user.role),
        employee_id=str(user.employee_id) if user.employee_id else None,
    )
    return TokenResponse(access_token=token, token_type="bearer")
