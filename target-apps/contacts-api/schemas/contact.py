"""Pydantic schemas for Contact endpoints."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class ContactCreate(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=120)
    email: EmailStr
    department_id: str
    phone: Optional[str] = Field(default=None, max_length=30)
    title: Optional[str] = Field(default=None, max_length=80)


class ContactUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    email: Optional[EmailStr] = None
    department_id: Optional[str] = None
    phone: Optional[str] = Field(default=None, max_length=30)
    title: Optional[str] = Field(default=None, max_length=80)


class ContactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    department_id: str
    full_name: str
    email: str
    phone: Optional[str] = None
    title: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @field_validator("id", "department_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v


class ContactListPage(BaseModel):
    items: list[ContactOut]
    total: int
    limit: int
    offset: int
