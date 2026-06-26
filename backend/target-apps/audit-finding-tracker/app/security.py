"""JWT authentication and password hashing utilities."""

from datetime import datetime, timedelta
from typing import Optional, Tuple

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str, role: str, expires_delta: Optional[timedelta] = None) -> Tuple[str, datetime]:
    """Create a JWT access token.
    
    Returns:
        Tuple of (token_string, expires_at)
    """
    settings = get_settings()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes)
    
    to_encode = {
        "sub": subject,  # user_id 
        "role": role,
        "exp": expire,
        "iat": datetime.utcnow()
    }
    
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt, expire


def decode_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT token.
    
    Returns:
        Token payload if valid, None if invalid/expired
    """
    settings = get_settings()
    
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError:
        return None