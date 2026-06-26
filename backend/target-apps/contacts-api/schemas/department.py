"""Department Pydantic schemas for request/response."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DepartmentBase(BaseModel):
    """Base department fields."""
    name: str = Field(..., min_length=1, max_length=80)
    code: str = Field(..., min_length=2, max_length=10, pattern=r"^[A-Z]{2,10}$")


class DepartmentCreate(DepartmentBase):
    """Request schema for creating departments."""
    pass


class DepartmentUpdate(BaseModel):
    """Request schema for updating departments."""
    name: Optional[str] = Field(None, min_length=1, max_length=80)
    code: Optional[str] = Field(None, min_length=2, max_length=10, pattern=r"^[A-Z]{2,10}$")


class DepartmentRead(DepartmentBase):
    """Response schema for departments."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    created_at: datetime

    @field_validator("id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v