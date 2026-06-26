"""Audit management endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import CurrentUser, require_auditor_or_executive
from app.models.audit import Audit
from schemas.audit import (
    AuditListResponse, 
    AuditResponse, 
    CreateAuditRequest
)

router = APIRouter()


@router.get("/", response_model=AuditListResponse)
def list_audits(
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auditor_or_executive)
):
    """List audits with optional filtering by status."""
    query = select(Audit)
    
    # Filter by status if provided
    if status:
        query = query.where(Audit.status == status)
    
    # Get total count
    count_query = select(func.count(Audit.id))
    if status:
        count_query = count_query.where(Audit.status == status)
    
    total = db.scalar(count_query) or 0
    
    # Get paginated results
    audits = list(db.scalars(query.offset(offset).limit(limit)).all())
    
    return AuditListResponse(
        audits=audits,
        total=total,
        limit=limit,
        offset=offset
    )


@router.post("/", response_model=AuditResponse, status_code=201)
def create_audit(
    body: CreateAuditRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auditor_or_executive)
):
    """Create a new audit."""
    audit = Audit(
        title=body.title,
        description=body.description,
        created_by=current_user.user_id
    )
    
    db.add(audit)
    db.commit()
    db.refresh(audit)
    
    return audit