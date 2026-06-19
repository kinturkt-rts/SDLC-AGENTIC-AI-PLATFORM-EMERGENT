"""Courses router — CRUD for HR admin."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import CurrentUser
from app.models.entities import AuditLog, Course
from app.models.pg_types import CourseCategory
from schemas.courses import CourseCreate, CourseOut, CourseUpdate

router = APIRouter(tags=["courses"])


def _require_hr_admin(current_user: CurrentUser) -> None:
    role = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if role != "hr_admin":
        raise HTTPException(status_code=403, detail="Forbidden")


@router.get("", response_model=list[CourseOut])
def list_courses(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[CourseOut]:
    """List courses (all authenticated roles)."""
    rows = db.scalars(select(Course).offset(offset).limit(limit)).all()
    return [CourseOut.model_validate(r) for r in rows]


@router.get("/{course_id}", response_model=CourseOut)
def get_course(
    course_id: str,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> CourseOut:
    """Get a single course."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return CourseOut.model_validate(course)


@router.post("", response_model=CourseOut, status_code=201)
def create_course(
    body: CourseCreate,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> CourseOut:
    """Create a course (HR admin only)."""
    _require_hr_admin(current_user)
    # Check duplicate name
    existing = db.query(Course).filter(Course.name == body.name).first()
    if existing:
        raise HTTPException(status_code=409, detail="Course name already exists")
    course = Course(
        id=str(uuid.uuid4()),
        name=body.name,
        category=body.category,
        validity_period_months=body.validity_period_months,
        required_for_all_staff=body.required_for_all_staff,
        certificate_ref=body.certificate_ref,
    )
    db.add(course)
    # Audit
    audit = AuditLog(
        id=str(uuid.uuid4()),
        user_id=str(current_user.id),
        action="CREATE",
        entity="course",
        entity_id=str(course.id),
        detail={"name": body.name},
    )
    db.add(audit)
    db.commit()
    db.refresh(course)
    return CourseOut.model_validate(course)


@router.patch("/{course_id}", response_model=CourseOut)
def update_course(
    course_id: str,
    body: CourseUpdate,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> CourseOut:
    """Update a course (HR admin only)."""
    _require_hr_admin(current_user)
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    updates = body.model_dump(exclude_unset=True)
    if "name" in updates and updates["name"] != course.name:
        dup = db.query(Course).filter(Course.name == updates["name"]).first()
        if dup:
            raise HTTPException(status_code=409, detail="Course name already exists")
    for k, v in updates.items():
        setattr(course, k, v)
    # Audit
    audit = AuditLog(
        id=str(uuid.uuid4()),
        user_id=str(current_user.id),
        action="UPDATE",
        entity="course",
        entity_id=str(course.id),
        detail=updates,
    )
    db.add(audit)
    db.commit()
    db.refresh(course)
    return CourseOut.model_validate(course)
