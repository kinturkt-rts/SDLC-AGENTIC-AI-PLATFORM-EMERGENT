"""Auth router — POST /auth/token (OAuth2 form login)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.security import create_access_token, verify_password
from schemas.auth import TokenResponse

router = APIRouter(tags=["auth"])


@router.post("/token", response_model=TokenResponse)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Authenticate via username/password form; return JWT."""
    user = db.query(User).filter(User.username == form.username).first()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    token, _ = create_access_token(
        subject=str(user.id),
        role=user.role,
        technician_id=str(user.technician_id) if user.technician_id else None,
    )
    return TokenResponse(access_token=token, role=user.role)
