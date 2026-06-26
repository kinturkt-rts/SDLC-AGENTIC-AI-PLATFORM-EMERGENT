"""Auth router — login endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.security import create_access_token, verify_password
from schemas.auth import LoginRequest, LoginResponse

router = APIRouter(tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    """Authenticate user and return JWT."""
    user = db.query(User).filter(User.username == body.username, User.is_active == True).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(subject=str(user.id), role=str(user.role))
    return LoginResponse(access_token=token, role=str(user.role))
