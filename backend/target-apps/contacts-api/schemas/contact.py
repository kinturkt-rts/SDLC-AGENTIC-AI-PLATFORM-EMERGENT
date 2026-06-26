"""Contact Pydantic schemas for request/response."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from schemas.department import DepartmentRead


class ContactBase(BaseModel):
    """Base contact fields."""
    full_name: str = Field(..., min_length=1, max_length=120)
    email: EmailStr
    phone: Optional[str] = Field(None, max_length=30)
    title: Optional[str] = Field(None, max_length=80)


class ContactCreate(ContactBase):
    """Request schema for creating contacts."""
    department_id: str


class ContactUpdate(BaseModel):
    """Request schema for updating contacts."""
    department_id: Optional[str] = None
    full_name: Optional[str] = Field(None, min_length=1, max_length=120)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=30)
    title: Optional[str] = Field(None, max_length=80)


class ContactRead(ContactBase):
    """Response schema for contacts."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    department_id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    department: Optional[DepartmentRead] = None

    @field_validator("id", "department_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v


class ContactListPage(BaseModel):
    """Paginated contact list response."""
    items: list[ContactRead]
    total: int
    limit: int
    offset: int