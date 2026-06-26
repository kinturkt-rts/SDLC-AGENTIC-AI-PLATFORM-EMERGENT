"""Auth request/response schemas."""
from __future__ import annotations

from pydantic import BaseModel


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
