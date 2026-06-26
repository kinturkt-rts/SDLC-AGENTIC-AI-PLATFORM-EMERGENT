"""ORM models for all training_compliance tables."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

from app.database import Base
from app.models.pg_types import course_category_enum, user_role_enum, uuid_pk


class Department(Base):
    __tablename__ = "departments"

    id = Column(uuid_pk(), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(Text, unique=True, nullable=False)


class JobRole(Base):
    __tablename__ = "job_roles"

    id = Column(uuid_pk(), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(Text, unique=True, nullable=False)


class Course(Base):
    __tablename__ = "courses"

    id = Column(uuid_pk(), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(Text, unique=True, nullable=False)
    category = Column(course_category_enum(), nullable=False)
    validity_period_months = Column(Integer, nullable=True)
    required_for_all_staff = Column(Boolean, nullable=False, default=False)
    certificate_ref = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)


class Employee(Base):
    __tablename__ = "employees"

    id = Column(uuid_pk(), primary_key=True, default=lambda: str(uuid.uuid4()))
    full_name = Column(Text, nullable=False)
    email = Column(Text, unique=True, nullable=False)
    department_id = Column(uuid_pk(), ForeignKey("departments.id"), nullable=False)
    job_role_id = Column(uuid_pk(), ForeignKey("job_roles.id"), nullable=False)
    manager_id = Column(uuid_pk(), ForeignKey("employees.id"), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)


class RoleRequirement(Base):
    __tablename__ = "role_requirements"

    id = Column(uuid_pk(), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_role_id = Column(uuid_pk(), ForeignKey("job_roles.id"), nullable=False)
    course_id = Column(uuid_pk(), ForeignKey("courses.id"), nullable=False)


class CompletionRecord(Base):
    __tablename__ = "completion_records"

    id = Column(uuid_pk(), primary_key=True, default=lambda: str(uuid.uuid4()))
    employee_id = Column(uuid_pk(), ForeignKey("employees.id"), nullable=False)
    course_id = Column(uuid_pk(), ForeignKey("courses.id"), nullable=False)
    completion_date = Column(Date, nullable=False)
    expiry_date = Column(Date, nullable=True)
    is_active_record = Column(Boolean, nullable=False, default=True)
    superseded_by_id = Column(uuid_pk(), ForeignKey("completion_records.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), default=datetime.utcnow)


class User(Base):
    __tablename__ = "users"

    id = Column(uuid_pk(), primary_key=True, default=lambda: str(uuid.uuid4()))
    employee_id = Column(uuid_pk(), ForeignKey("employees.id"), nullable=True)
    email = Column(Text, unique=True, nullable=False)
    hashed_password = Column(Text, nullable=False)
    role = Column(user_role_enum(), nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(uuid_pk(), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(uuid_pk(), nullable=False)
    action = Column(Text, nullable=False)
    entity = Column(Text, nullable=True)
    entity_id = Column(uuid_pk(), nullable=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), default=datetime.utcnow)
    detail = Column(JSONB().with_variant(JSON(), "sqlite"), nullable=True)
