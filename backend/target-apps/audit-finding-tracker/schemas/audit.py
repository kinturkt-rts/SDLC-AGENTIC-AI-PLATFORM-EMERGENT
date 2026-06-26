"""Pydantic schemas for audit endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, field_validator


class AuditBase(BaseModel):
    """Base audit fields."""
    title: str
    description: Optional[str] = None


class CreateAuditRequest(AuditBase):
    """Request to create a new audit."""
    pass


class AuditResponse(BaseModel):
    """Audit response model."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    title: str
    description: Optional[str]
    status: str
    created_by: str
    created_at: datetime
    version: int
    
    @field_validator("id", "created_by", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v


class AuditListParams(BaseModel):
    """Query parameters for audit list endpoint."""
    status: Optional[str] = None
    limit: int = 20
    offset: int = 0


class AuditListResponse(BaseModel):
    """Paginated audit list response."""
    audits: List[AuditResponse]
    total: int
    limit: int
    offset: int