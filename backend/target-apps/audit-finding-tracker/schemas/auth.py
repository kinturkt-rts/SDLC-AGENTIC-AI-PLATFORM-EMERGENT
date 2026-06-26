"""Pydantic schemas for authentication endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator


class LoginRequest(BaseModel):
    """Login request with email and password."""
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """User information in auth responses."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    email: str
    role: str
    created_at: datetime
    
    @field_validator("id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v


class TokenResponse(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserResponse