"""Requirements router — role-to-course requirement matrix."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import CurrentUser
from app.models.entities import AuditLog, RoleRequirement
from schemas.requirements import RequirementCreate, RequirementOut

router = APIRouter(tags=["requirements"])


def _require_hr_admin(current_user: CurrentUser) -> None:
    role = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if role != "hr_admin":
        raise HTTPException(status_code=403, detail="Forbidden")


@router.get("", response_model=list[RequirementOut])
def list_requirements(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[RequirementOut]:
    """List all role requirements."""
    rows = db.scalars(select(RoleRequirement).offset(offset).limit(limit)).all()
    return [RequirementOut.model_validate(r) for r in rows]


@router.post("", response_model=RequirementOut, status_code=201)
def create_requirement(
    body: RequirementCreate,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> RequirementOut:
    """Create a role requirement (HR admin only). 409 on duplicate."""
    _require_hr_admin(current_user)
    existing = db.query(RoleRequirement).filter(
        RoleRequirement.job_role_id == body.job_role_id,
        RoleRequirement.course_id == body.course_id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Requirement already exists")
    req = RoleRequirement(
        id=str(uuid.uuid4()),
        job_role_id=body.job_role_id,
        course_id=body.course_id,
    )
    db.add(req)
    audit = AuditLog(
        id=str(uuid.uuid4()),
        user_id=str(current_user.id),
        action="CREATE",
        entity="role_requirement",
        entity_id=str(req.id),
        detail={"job_role_id": body.job_role_id, "course_id": body.course_id},
    )
    db.add(audit)
    db.commit()
    db.refresh(req)
    return RequirementOut.model_validate(req)


@router.delete("/{requirement_id}", status_code=204, response_model=None)
def delete_requirement(
    requirement_id: str,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> None:
    """Delete a role requirement (HR admin only)."""
    _require_hr_admin(current_user)
    req = db.query(RoleRequirement).filter(RoleRequirement.id == requirement_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Requirement not found")
    db.delete(req)
    audit = AuditLog(
        id=str(uuid.uuid4()),
        user_id=str(current_user.id),
        action="DELETE",
        entity="role_requirement",
        entity_id=str(requirement_id),
        detail={},
    )
    db.add(audit)
    db.commit()
