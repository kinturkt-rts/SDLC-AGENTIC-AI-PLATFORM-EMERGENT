"""Student CRUD + deactivate routes."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import ReadKey, WriteKey
from app.models.student import Student
from schemas.student import StudentCreate, StudentOut, StudentUpdate

router = APIRouter()


# ── POST /api/v1/students (create) ─────────────────────────────────────
@router.post("", response_model=StudentOut, status_code=201)
def create_student(
    body: StudentCreate,
    _key: WriteKey,
    db: Session = Depends(get_db),
) -> Student:
    student = Student(
        student_id=body.student_id,
        full_name=body.full_name,
        email=body.email,
        course=body.course,
        enrollment_date=body.enrollment_date,
        status=body.status,
        is_active=body.status == "active",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(student)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A student with this student_id or email already exists",
        )
    db.refresh(student)
    return student


# ── GET /api/v1/students (list with optional filters) ────────────────────
@router.get("", response_model=list[StudentOut])
def list_students(
    _key: ReadKey,
    db: Session = Depends(get_db),
    course: Optional[str] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
) -> list[Student]:
    stmt = select(Student)
    if course:
        stmt = stmt.where(Student.course == course)
    if status_filter:
        stmt = stmt.where(Student.status == status_filter)
    return list(db.scalars(stmt).all())


# ── GET /api/v1/students/{student_id} ──────────────────────────────────
@router.get("/{student_id}", response_model=StudentOut)
def get_student(
    student_id: str,
    _key: ReadKey,
    db: Session = Depends(get_db),
) -> Student:
    student = db.scalars(
        select(Student).where(Student.student_id == student_id)
    ).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )
    return student


# ── PUT /api/v1/students/{student_id} ──────────────────────────────────
@router.put("/{student_id}", response_model=StudentOut)
def update_student(
    student_id: str,
    body: StudentUpdate,
    _key: WriteKey,
    db: Session = Depends(get_db),
) -> Student:
    student = db.scalars(
        select(Student).where(Student.student_id == student_id)
    ).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )

    updates = body.model_dump(exclude_unset=True)

    # Reject attempt to change student_id (immutable)
    if "student_id" in updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="student_id is immutable and cannot be changed",
        )

    for field, value in updates.items():
        setattr(student, field, value)

    # Sync is_active with status
    if "status" in updates:
        student.is_active = updates["status"] == "active"

    student.updated_at = datetime.now(timezone.utc)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A student with this email already exists",
        )
    db.refresh(student)
    return student


# ── PATCH /api/v1/students/{student_id}/deactivate ──────────────────────
@router.patch("/{student_id}/deactivate", response_model=StudentOut)
def deactivate_student(
    student_id: str,
    _key: WriteKey,
    db: Session = Depends(get_db),
) -> Student:
    student = db.scalars(
        select(Student).where(Student.student_id == student_id)
    ).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )
    student.status = "inactive"
    student.is_active = False
    student.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(student)
    return student
