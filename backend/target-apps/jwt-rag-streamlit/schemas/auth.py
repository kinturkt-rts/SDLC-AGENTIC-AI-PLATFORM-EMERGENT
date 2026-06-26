from pydantic import BaseModel, Field
from typing import List
from app.models.pg_types import UserRole


class TokenRequest(BaseModel):
    email: str = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration in seconds")


class UserProfile(BaseModel):
    id: int
    email: str
    role: UserRole
    collections: List[int] = Field(default=[], description="Accessible collection IDs")
    
    class Config:
        from_attributes = True
