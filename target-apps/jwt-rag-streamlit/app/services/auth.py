import bcrypt
from datetime import datetime, timedelta
from jose import JWTError, jwt
from fastapi import HTTPException
from app.config import get_settings
from app.models.user import User
from app.models.pg_types import UserRole, UserStatus


def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def verify_password(password: str, hashed: str) -> bool:
    """Verify password against hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))


# def _role_value(role: UserRole | str) -> str:
#     return role.value if isinstance(role, UserRole) else str(role)


def create_access_token(user: User) -> str:
    """Create JWT access token for user"""
    settings = get_settings()
    
    # Token payload
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role.value,
        "exp": datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes),
        "iat": datetime.utcnow()
    }
    
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Decode and validate JWT token"""
    settings = get_settings()
    
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def authenticate_user(db, email: str, password: str) -> User:
    """Authenticate user by email and password"""
    user = db.query(User).filter(User.email == email).first()
    
    # active = (
    #     user.status == UserStatus.active
    #     if isinstance(user.status, UserStatus)
    #     else user.status == UserStatus.active.value
    # )
    if not user or user.status != UserStatus.active:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    return user