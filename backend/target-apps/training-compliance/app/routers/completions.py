"""Completions router — record training completions with recertification logic."""
from __future__ import annotations

import uuid
from datetime import date

from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import CurrentUser
from app.models.entities import AuditLog, CompletionRecord, Course, Employee
from schemas.completions import CompletionCreate, CompletionOut

router = APIRouter(tags=["completions"])


@router.post("", response_model=CompletionOut, status_code=201)
def create_completion(
    body: CompletionCreate,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> CompletionOut:
    """Record a training completion. HR admin can record for anyone; employees only for themselves."""
    role = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    # Employees can only record their own completions
    if role == "employee":
        if str(current_user.employee_id) != body.employee_id:
            raise HTTPException(status_code=403, detail="Forbidden")
    elif role not in ("hr_admin",):
        raise HTTPException(status_code=403, detail="Forbidden")

    # Validate employee exists
    employee = db.query(Employee).filter(Employee.id == body.employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Validate course exists
    course = db.query(Course).filter(Course.id == body.course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Calculate expiry date
    expiry_date = None
    if course.validity_period_months:
        expiry_date = body.completion_date + relativedelta(months=course.validity_period_months)

    # New record ID
    new_id = str(uuid.uuid4())

    # Find prior active record (before inserting the new one)
    prior = db.query(CompletionRecord).filter(
        CompletionRecord.employee_id == body.employee_id,
        CompletionRecord.course_id == body.course_id,
        CompletionRecord.is_active_record == True,  # noqa: E712
    ).first()

    # Insert new record first (so FK reference is valid)
    record = CompletionRecord(
        id=new_id,
        employee_id=body.employee_id,
        course_id=body.course_id,
        completion_date=body.completion_date,
        expiry_date=expiry_date,
        is_active_record=True,
    )
    db.add(record)
    db.flush()  # Make the new record visible for FK resolution

    # Now supersede the prior record (FK to new_id is now valid)
    if prior:
        prior.is_active_record = False
        prior.superseded_by_id = new_id

    # Audit
    audit = AuditLog(
        id=str(uuid.uuid4()),
        user_id=str(current_user.id),
        action="CREATE",
        entity="completion_record",
        entity_id=new_id,
        detail={
            "employee_id": body.employee_id,
            "course_id": body.course_id,
            "completion_date": str(body.completion_date),
        },
    )
    db.add(audit)
    db.commit()
    db.refresh(record)
    return CompletionOut.model_validate(record)
