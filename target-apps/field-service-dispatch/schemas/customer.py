"""Customer and ServiceAddress schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class ServiceAddressCreate(BaseModel):
    street: str
    city: str
    state: str
    postal_code: str


class ServiceAddressOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    customer_id: str
    street: str
    city: str
    state: str
    postal_code: str

    @field_validator("id", "customer_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v


class CustomerCreate(BaseModel):
    full_name: str
    phone: str
    email: Optional[str] = None
    service_addresses: list[ServiceAddressCreate]


class CustomerUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    is_active: Optional[bool] = None


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    full_name: str
    phone: str
    email: Optional[str] = None
    is_active: bool
    created_at: datetime
    service_addresses: list[ServiceAddressOut] = []

    @field_validator("id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v
