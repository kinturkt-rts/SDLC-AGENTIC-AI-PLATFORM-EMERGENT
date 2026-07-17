"""Customer schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class CustomerCreate(BaseModel):
    full_name: str
    phone: str
    email: Optional[str] = None
    street: str
    city: str
    state: str
    zip: str


class CustomerUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    full_name: str
    phone: str
    email: Optional[str] = None
    street: str
    city: str
    state: str
    zip: str
    created_at: datetime
    deleted_at: Optional[datetime] = None

    @field_validator("id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v
