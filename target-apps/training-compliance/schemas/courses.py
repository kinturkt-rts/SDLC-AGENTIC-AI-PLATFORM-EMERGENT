"""Pydantic schemas for courses."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class CourseCreate(BaseModel):
    name: str
    category: str
    validity_period_months: Optional[int] = None
    required_for_all_staff: bool = False
    certificate_ref: Optional[str] = None


class CourseUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    validity_period_months: Optional[int] = None
    required_for_all_staff: Optional[bool] = None
    certificate_ref: Optional[str] = None
    is_active: Optional[bool] = None


class CourseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    category: str
    validity_period_months: Optional[int] = None
    required_for_all_staff: bool
    certificate_ref: Optional[str] = None
    is_active: bool

    @field_validator("id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v

    @field_validator("category", mode="before")
    @classmethod
    def coerce_category(cls, v):
        return str(v.value) if hasattr(v, "value") else str(v) if v else v
