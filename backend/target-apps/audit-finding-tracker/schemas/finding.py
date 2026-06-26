"""Pydantic schemas for finding endpoints."""

from __future__ import annotations

from datetime import datetime, date
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, field_validator


class FindingBase(BaseModel):
    """Base finding fields."""
    title: str
    description: Optional[str] = None
    severity: str
    assigned_to: Optional[str] = None
    due_date: Optional[date] = None


class CreateFindingRequest(FindingBase):
    """Request to create a new finding."""
    audit_id: str


class UpdateStatusRequest(BaseModel):
    """Request to update finding status."""
    status: str
    comment: Optional[str] = None


class FindingResponse(BaseModel):
    """Finding response model."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    audit_id: str
    title: str
    description: Optional[str]
    severity: str
    status: str
    assigned_to: Optional[str]
    due_date: Optional[date]
    created_by: str
    created_at: datetime
    version: int
    
    @field_validator("id", "audit_id", "assigned_to", "created_by", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v


class FindingListParams(BaseModel):
    """Query parameters for finding list endpoint."""
    audit_id: Optional[str] = None
    status: Optional[str] = None
    assigned_to: Optional[str] = None
    severity: Optional[str] = None
    limit: int = 20
    offset: int = 0


class FindingListResponse(BaseModel):
    """Paginated finding list response."""
    findings: List[FindingResponse]
    total: int
    limit: int
    offset: int


class StatusHistoryResponse(BaseModel):
    """Status history entry response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    finding_id: str
    from_status: Optional[str]
    to_status: str
    changed_by: str
    changed_at: datetime
    comment: Optional[str]
    
    @field_validator("id", "finding_id", "changed_by", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v


class StatusHistoryListResponse(BaseModel):
    """Status history list response."""
    history: List[StatusHistoryResponse]


class CreateCommentRequest(BaseModel):
    """Request to create a finding comment."""
    content: str
    parent_id: Optional[str] = None


class CommentResponse(BaseModel):
    """Finding comment response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    finding_id: str
    author_id: str
    content: str
    created_at: datetime
    parent_id: Optional[str]
    
    @field_validator("id", "finding_id", "author_id", "parent_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v