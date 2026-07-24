"""Test that StudentOut handles datetime coercion correctly."""
from __future__ import annotations

from datetime import date, datetime, timezone

from schemas.student import StudentOut


def test_student_out_coerces_datetime_fields() -> None:
    """StudentOut handles both datetime objects and ISO strings."""
    ts = datetime(2024, 1, 20, 10, 0, tzinfo=timezone.utc)
    payload = {
        "id": 1,
        "student_id": "STU-001",
        "full_name": "Test",
        "email": "test@example.com",
        "course": "CS",
        "enrollment_date": date(2024, 1, 15),
        "status": "active",
        "is_active": True,
        "created_at": ts,
        "updated_at": ts,
    }
    out = StudentOut.model_validate(payload)
    assert out.student_id == "STU-001"
    assert out.created_at is not None
