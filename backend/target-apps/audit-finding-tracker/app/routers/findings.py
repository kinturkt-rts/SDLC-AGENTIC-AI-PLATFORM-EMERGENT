"""Finding management endpoints with status workflow."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status, UploadFile, File
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import AuthUser
from app.models.finding import Finding
from app.models.status_history import StatusHistory
from app.models.finding_comment import FindingComment
from app.models.evidence_file import EvidenceFile
from app.services.file_storage import file_storage_service
from schemas.finding import (
    CreateFindingRequest,
    FindingListResponse,
    FindingResponse,
    StatusHistoryListResponse,
    UpdateStatusRequest,
    CommentResponse,
    CreateCommentRequest
)
from schemas.evidence import EvidenceResponse

router = APIRouter()

# Valid status transitions per design §5
VALID_TRANSITIONS = {
    "draft": ["assigned"],
    "assigned": ["in_progress"], 
    "in_progress": ["pending_verification", "assigned"],
    "pending_verification": ["verified", "in_progress"],
    "verified": ["closed"],
    "closed": []
}


def _check_finding_access(finding: Finding, current_user: AuthUser) -> None:
    """Check if user has access to the finding per role-based rules."""
    if current_user.role == "assignee":
        # Assignees can only access findings assigned to them
        if finding.assigned_to != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied - finding not assigned to you"
            )
    # Auditors and executives can access all findings


@router.get("/", response_model=FindingListResponse)
def list_findings(
    audit_id: Optional[str] = Query(default=None),
    status_param: Optional[str] = Query(default=None, alias="status"),
    assigned_to: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: AuthUser = None
):
    """List findings with role-scoped data access."""
    query = select(Finding)
    
    # Role-based filtering
    if current_user and current_user.role == "assignee":
        # Assignees see only their assigned findings
        query = query.where(Finding.assigned_to == current_user.user_id)
    
    # Apply filters
    if audit_id:
        query = query.where(Finding.audit_id == audit_id)
    if status_param:
        query = query.where(Finding.status == status_param)
    if assigned_to and current_user and current_user.role != "assignee":
        # Only auditors/executives can filter by assignee
        query = query.where(Finding.assigned_to == assigned_to)
    if severity:
        query = query.where(Finding.severity == severity)
    
    # Count query with same filters
    count_query = select(func.count(Finding.id))
    if current_user and current_user.role == "assignee":
        count_query = count_query.where(Finding.assigned_to == current_user.user_id)
    if audit_id:
        count_query = count_query.where(Finding.audit_id == audit_id)
    if status_param:
        count_query = count_query.where(Finding.status == status_param)
    if assigned_to and current_user and current_user.role != "assignee":
        count_query = count_query.where(Finding.assigned_to == assigned_to)
    if severity:
        count_query = count_query.where(Finding.severity == severity)
    
    total = db.scalar(count_query) or 0
    findings = list(db.scalars(query.offset(offset).limit(limit)).all())
    
    return FindingListResponse(
        findings=findings,
        total=total,
        limit=limit,
        offset=offset
    )


@router.post("/", response_model=FindingResponse, status_code=201)
def create_finding(
    body: CreateFindingRequest,
    db: Session = Depends(get_db),
    current_user: AuthUser = None
):
    """Create a new finding."""
    # Only auditors can create findings
    if not current_user or current_user.role != "auditor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only auditors can create findings"
        )
    
    finding = Finding(
        audit_id=body.audit_id,
        title=body.title,
        description=body.description,
        severity=body.severity,
        assigned_to=body.assigned_to,
        due_date=body.due_date,
        created_by=current_user.user_id
    )
    
    db.add(finding)
    db.commit()
    db.refresh(finding)
    
    # Create initial status history entry
    history = StatusHistory(
        finding_id=finding.id,
        from_status=None,
        to_status="draft",
        changed_by=current_user.user_id,
        comment="Finding created"
    )
    db.add(history)
    db.commit()
    
    return finding


@router.put("/{id}/status", response_model=FindingResponse)
def update_finding_status(
    id: str,
    body: UpdateStatusRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: AuthUser = None
):
    """Update finding status with optimistic locking."""
    finding = db.query(Finding).filter(Finding.id == id).first()
    if not finding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Finding not found"
        )
    
    _check_finding_access(finding, current_user)
    
    # Check If-Match header for optimistic locking
    if_match = request.headers.get("If-Match")
    if not if_match:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="If-Match header required for optimistic locking"
        )
    
    try:
        expected_version = int(if_match.strip('"'))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid If-Match header format"
        )
    
    if finding.version != expected_version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Version mismatch. Expected {expected_version}, current {finding.version}"
        )
    
    # Validate status transition
    if body.status not in VALID_TRANSITIONS.get(finding.status, []):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid transition from {finding.status} to {body.status}"
        )
    
    # Check evidence requirement for pending_verification
    if body.status == "pending_verification":
        evidence_count = db.scalar(
            select(func.count(EvidenceFile.id)).where(EvidenceFile.finding_id == finding.id)
        ) or 0
        if evidence_count == 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Evidence files required before transitioning to pending_verification"
            )
    
    # Update finding
    old_status = finding.status
    finding.status = body.status
    finding.version += 1
    
    # Create status history entry
    history = StatusHistory(
        finding_id=finding.id,
        from_status=old_status,
        to_status=body.status,
        changed_by=current_user.user_id,
        comment=body.comment
    )
    
    db.add(history)
    db.commit()
    db.refresh(finding)
    
    return finding


@router.get("/{id}/history", response_model=StatusHistoryListResponse)
def get_finding_history(
    id: str,
    db: Session = Depends(get_db),
    current_user: AuthUser = None
):
    """Get immutable audit trail for a finding."""
    finding = db.query(Finding).filter(Finding.id == id).first()
    if not finding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Finding not found"
        )
    
    _check_finding_access(finding, current_user)
    
    history = list(db.scalars(
        select(StatusHistory)
        .where(StatusHistory.finding_id == id)
        .order_by(StatusHistory.changed_at.desc())
    ).all())
    
    return StatusHistoryListResponse(history=history)


@router.post("/{id}/evidence", response_model=EvidenceResponse, status_code=201)
async def upload_evidence(
    id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: AuthUser = None
):
    """Upload evidence file for a finding."""
    finding = db.query(Finding).filter(Finding.id == id).first()
    if not finding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Finding not found"
        )
    
    _check_finding_access(finding, current_user)
    
    # Validate file
    try:
        file_storage_service.validate_file(file)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    # Store file
    s3_key, local_path = await file_storage_service.store_file(file, id)
    
    # Get file size
    file_content = await file.read()
    file_size = len(file_content)
    
    # Reset file pointer and save metadata
    await file.seek(0)
    
    evidence = EvidenceFile(
        finding_id=id,
        filename=file.filename or "unnamed",
        s3_key=s3_key,
        file_size=file_size,
        mime_type=file.content_type or "application/octet-stream",
        uploaded_by=current_user.user_id
    )
    
    db.add(evidence)
    db.commit()
    db.refresh(evidence)
    
    return evidence


@router.post("/{id}/comments", response_model=CommentResponse, status_code=201)
def create_comment(
    id: str,
    body: CreateCommentRequest,
    db: Session = Depends(get_db),
    current_user: AuthUser = None
):
    """Create a comment on a finding."""
    finding = db.query(Finding).filter(Finding.id == id).first()
    if not finding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Finding not found"
        )
    
    _check_finding_access(finding, current_user)
    
    comment = FindingComment(
        finding_id=id,
        author_id=current_user.user_id,
        content=body.content,
        parent_id=body.parent_id
    )
    
    db.add(comment)
    db.commit()
    db.refresh(comment)
    
    return comment