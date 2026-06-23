from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.orm import Session
from app.dependencies import DbSession
from app.models.user import User
from app.models.collection import CollectionMembership
from app.services.auth import authenticate_user, create_access_token
from app.services.audit import log_audit_event
from app.config import get_settings
from schemas.auth import TokenRequest, TokenResponse, UserProfile
from app.dependencies import CurrentUser

router = APIRouter()


@router.post("/token", response_model=TokenResponse)
def login(request: Request, body: TokenRequest, db: DbSession):
    """Authenticate user and return JWT token"""
    settings = get_settings()
    
    try:
        # Authenticate user
        user = authenticate_user(db, body.email, body.password)
        
        # Create access token
        access_token = create_access_token(user)
        
        # Log successful login
        log_audit_event(
            db=db,
            user_id=user.id,
            action="login_success",
            ip_address=request.client.host if request.client else None
        )
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.jwt_expire_minutes * 60
        )
        
    except HTTPException as e:
        # Log failed login attempt
        log_audit_event(
            db=db,
            user_id=None,
            action="login_failed",
            details={"email": body.email, "reason": e.detail},
            ip_address=request.client.host if request.client else None
        )
        raise e


@router.get("/me", response_model=UserProfile)
def get_current_user_profile(current_user: CurrentUser, db: DbSession):
    """Get current user profile with accessible collections"""
    # Get user's collections (owned + memberships)
    owned_collections = db.query(CollectionMembership.collection_id).filter(
        CollectionMembership.user_id == current_user.id
    ).all()
    
    collection_ids = [cm.collection_id for cm in owned_collections]
    
    return UserProfile(
        id=current_user.id,
        email=current_user.email,
        role=current_user.role,
        collections=collection_ids
    )
