"""Authentication endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.security import create_access_token, verify_password
from schemas.auth import LoginRequest, TokenResponse, UserResponse

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
def login(
    credentials: LoginRequest,
    db: Session = Depends(get_db)
):
    """Authenticate user and return JWT token.
    
    Note: This is a simplified login for MVP. Production should integrate 
    with AWS Cognito per design document.
    """
    # For MVP, we'll do a simple email lookup
    # Production: Validate with Cognito and map to local user
    user = db.query(User).filter(User.email == credentials.email).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # For MVP, we'll use a simple password check
    # Production: This would be handled by Cognito
    # Simple demo - accept "password" for any user
    if credentials.password != "password":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Create JWT token
    access_token, expires_at = create_access_token(
        subject=user.id,
        role=user.role
    )
    
    return TokenResponse(
        access_token=access_token,
        expires_at=expires_at,
        user=UserResponse.model_validate(user)
    )