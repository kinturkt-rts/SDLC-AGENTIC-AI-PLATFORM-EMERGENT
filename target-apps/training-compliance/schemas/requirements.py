"""Pydantic schemas for role requirements."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator


class RequirementCreate(BaseModel):
    job_role_id: str
    course_id: str


class RequirementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_role_id: str
    course_id: str

    @field_validator("id", "job_role_id", "course_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v
