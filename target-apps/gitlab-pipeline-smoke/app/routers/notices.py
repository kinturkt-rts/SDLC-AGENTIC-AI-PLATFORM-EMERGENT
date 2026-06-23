"""Notice management endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.exc import IntegrityError

from app.dependencies import AuthKey, DbSession
from app.models import Category, Notice
from schemas.notice import NoticeCreate, NoticeListPage, NoticeOut, NoticeUpdate

router = APIRouter()


@router.post("/", response_model=NoticeOut, status_code=201)
def create_notice(
    body: NoticeCreate,
    db: DbSession,
    _auth_key: AuthKey,
) -> Notice:
    """Create a new notice (requires API key)."""
    # Verify category exists
    category = db.get(Category, body.category_id)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )
    
    # Validate date range
    if body.ends_at and body.starts_at and body.ends_at < body.starts_at:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="ends_at must be greater than or equal to starts_at",
        )
    
    notice = Notice(
        id=str(uuid.uuid4()),
        category_id=body.category_id,
        title=body.title,
        body=body.body,
        author_name=body.author_name,
        starts_at=body.starts_at or datetime.utcnow(),
        ends_at=body.ends_at,
        is_archived=False,
    )
    
    db.add(notice)
    try:
        db.commit()
        db.refresh(notice)
        return notice
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Failed to create notice",
        )


@router.get("/", response_model=NoticeListPage)
def list_notices(
    db: DbSession,
    active_only: bool = Query(default=True, description="Filter to active notices only"),
    category_id: str | None = Query(default=None, description="Filter by category ID"),
    q: str | None = Query(default=None, description="Search in title or body"),
    limit: int = Query(default=20, ge=1, le=100, description="Number of results to return"),
    offset: int = Query(default=0, ge=0, description="Number of results to skip"),
) -> NoticeListPage:
    """List notices with filtering and pagination."""
    query = select(Notice)
    count_query = select(func.count(Notice.id))
    
    filters = []
    
    # Active filter
    if active_only:
        now = datetime.utcnow()
        filters.append(
            and_(
                Notice.is_archived.is_(False),
                or_(Notice.starts_at.is_(None), Notice.starts_at <= now),
                or_(Notice.ends_at.is_(None), Notice.ends_at >= now),
            )
        )
    
    # Category filter
    if category_id:
        filters.append(Notice.category_id == category_id)
    
    # Search filter
    if q:
        search_term = f"%{q}%"
        filters.append(
            or_(
                Notice.title.ilike(search_term),
                Notice.body.ilike(search_term),
            )
        )
    
    if filters:
        query = query.where(and_(*filters))
        count_query = count_query.where(and_(*filters))
    
    # Count total
    total = db.scalar(count_query) or 0
    
    # Apply pagination and ordering
    query = query.order_by(Notice.created_at.desc()).offset(offset).limit(limit)
    
    notices = list(db.scalars(query).all())
    
    return NoticeListPage(
        items=notices,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{id}", response_model=NoticeOut)
def get_notice(id: str, db: DbSession) -> Notice:
    """Get notice by ID."""
    notice = db.get(Notice, id)
    if not notice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notice not found",
        )
    return notice


@router.patch("/{id}", response_model=NoticeOut)
def update_notice(
    id: str,
    body: NoticeUpdate,
    db: DbSession,
    _auth_key: AuthKey,
) -> Notice:
    """Update notice (requires API key)."""
    notice = db.get(Notice, id)
    if not notice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notice not found",
        )
    
    # Verify category exists if being updated
    if body.category_id:
        category = db.get(Category, body.category_id)
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found",
            )
    
    # Apply updates
    updates = body.model_dump(exclude_unset=True)
    for k, v in updates.items():
        setattr(notice, k, v)
    
    # Validate date range after updates
    if notice.ends_at and notice.starts_at and notice.ends_at < notice.starts_at:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="ends_at must be greater than or equal to starts_at",
        )
    
    # Update timestamp
    notice.updated_at = datetime.utcnow()
    
    try:
        db.commit()
        db.refresh(notice)
        return notice
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Failed to update notice",
        )


@router.post("/{id}/archive", status_code=204)
def archive_notice(
    id: str,
    db: DbSession,
    _auth_key: AuthKey,
) -> None:
    """Archive notice (requires API key, idempotent)."""
    notice = db.get(Notice, id)
    if not notice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notice not found",
        )
    
    # Idempotent - already archived is OK
    if not notice.is_archived:
        notice.is_archived = True
        notice.updated_at = datetime.utcnow()
        db.commit()
    
    return None