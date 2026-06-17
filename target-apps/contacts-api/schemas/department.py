"""Pydantic schemas for Department endpoints."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DepartmentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    code: str = Field(..., min_length=2, max_length=10)

    @field_validator("code")
    @classmethod
    def code_must_be_uppercase(cls, v: str) -> str:
        upper = v.upper()
        if not upper.isalpha():
            raise ValueError("code must contain only letters A-Z")
        return upper


class DepartmentUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    code: Optional[str] = Field(default=None, min_length=2, max_length=10)

    @field_validator("code")
    @classmethod
    def code_must_be_uppercase(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        upper = v.upper()
        if not upper.isalpha():
            raise ValueError("code must contain only letters A-Z")
        return upper


class DepartmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    code: str
    created_at: datetime

    @field_validator("id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v


class DepartmentDetailOut(DepartmentOut):
    """Includes contact_count for GET /departments/{id}."""
    contact_count: int = 0
