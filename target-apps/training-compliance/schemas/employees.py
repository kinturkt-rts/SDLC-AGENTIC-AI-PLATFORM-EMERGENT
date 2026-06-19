"""Pydantic schemas for employees."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class EmployeeCreate(BaseModel):
    full_name: str
    email: str
    department_id: str
    job_role_id: str
    manager_id: Optional[str] = None


class EmployeeUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    department_id: Optional[str] = None
    job_role_id: Optional[str] = None
    manager_id: Optional[str] = None
    is_active: Optional[bool] = None


class EmployeeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    full_name: str
    email: str
    department_id: str
    job_role_id: str
    manager_id: Optional[str] = None
    is_active: bool

    @field_validator("id", "department_id", "job_role_id", "manager_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v
