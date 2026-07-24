"""Seed data endpoint."""
from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import ReadKey, WriteKey
from app.models.student import Student
from schemas.student import SeedResponse

router = APIRouter()


@router.get("", response_model=SeedResponse)
def get_seed_status(
    _key: ReadKey,
    db: Session = Depends(get_db),
) -> dict:
    """Return how many of the 3 standard seed records already exist."""
    seed_ids = ["STU-001", "STU-002", "STU-003"]
    count = 0
    for sid in seed_ids:
        exists = db.scalars(select(Student).where(Student.student_id == sid)).first()
        if exists:
            count += 1
    return {"seeded": count}


@router.post("", response_model=SeedResponse)
def seed_students(
    _key: WriteKey,
    db: Session = Depends(get_db),
) -> dict:
    seed_data = [
        ("STU-001", "Alice Nguyen", "alice@example.com", "Computer Science", "2024-01-15", "active"),
        ("STU-002", "Ben Carter", "ben@example.com", "Data Engineering", "2024-03-01", "active"),
        ("STU-003", "Cleo Marsh", "cleo@example.com", "Cybersecurity", "2023-09-10", "inactive"),
    ]
    inserted = 0
    for sid, name, email, course, enroll, sts in seed_data:
        existing = db.scalars(
            select(Student).where(Student.student_id == sid)
        ).first()
        if not existing:
            student = Student(
                student_id=sid,
                full_name=name,
                email=email,
                course=course,
                enrollment_date=date.fromisoformat(enroll),
                status=sts,
                is_active=(sts == "active"),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(student)
            inserted += 1
    db.commit()
    return {"seeded": inserted}
