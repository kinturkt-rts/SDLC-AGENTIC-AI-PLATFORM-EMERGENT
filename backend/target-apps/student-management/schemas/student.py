"""Pydantic schemas for Student CRUD."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator


class StudentCreate(BaseModel):
    """Request body for POST /api/v1/students."""
    student_id: str
    full_name: str
    email: EmailStr
    course: str
    enrollment_date: date
    status: str = "active"

    @field_validator("enrollment_date")
    @classmethod
    def enrollment_not_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("enrollment_date must not be in the future")
        return v

    @field_validator("status")
    @classmethod
    def valid_status(cls, v: str) -> str:
        if v not in ("active", "inactive"):
            raise ValueError("status must be 'active' or 'inactive'")
        return v


class StudentUpdate(BaseModel):
    """Request body for PUT /api/v1/students/{student_id}.

    student_id is NOT included — it is immutable.
    """
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    course: Optional[str] = None
    enrollment_date: Optional[date] = None
    status: Optional[str] = None

    @field_validator("enrollment_date")
    @classmethod
    def enrollment_not_future(cls, v: date | None) -> date | None:
        if v is not None and v > date.today():
            raise ValueError("enrollment_date must not be in the future")
        return v

    @field_validator("status")
    @classmethod
    def valid_status(cls, v: str | None) -> str | None:
        if v is not None and v not in ("active", "inactive"):
            raise ValueError("status must be 'active' or 'inactive'")
        return v


class StudentOut(BaseModel):
    """Response schema for a single student."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: str
    full_name: str
    email: str
    course: str
    enrollment_date: date
    status: str
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SeedResponse(BaseModel):
    """Response for POST /api/v1/students/seed."""
    seeded: int
