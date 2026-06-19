"""Shared Postgres-specific column type helpers for SQLAlchemy models."""
from __future__ import annotations

import enum

from sqlalchemy import String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


# ── ENUM types ────────────────────────────────────────────────────────────────

class CourseCategory(str, enum.Enum):
    safety = "safety"
    security = "security"
    role_specific = "role_specific"


class UserRole(str, enum.Enum):
    hr_admin = "hr_admin"
    manager = "manager"
    employee = "employee"
    compliance_officer = "compliance_officer"


# ── Column type factories ─────────────────────────────────────────────────────

def uuid_pk():
    """UUID primary key column type with SQLite variant."""
    return PG_UUID(as_uuid=False).with_variant(String(36), "sqlite")


def course_category_enum():
    """ENUM column for course_category with SQLite String variant."""
    return SAEnum(
        CourseCategory,
        name="course_category",
        schema="training_compliance",
        create_type=False,
        native_enum=True,
    ).with_variant(String(20), "sqlite")


def user_role_enum():
    """ENUM column for user_role with SQLite String variant."""
    return SAEnum(
        UserRole,
        name="user_role",
        schema="training_compliance",
        create_type=False,
        native_enum=True,
    ).with_variant(String(20), "sqlite")
