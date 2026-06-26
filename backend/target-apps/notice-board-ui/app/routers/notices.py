"""Notice routes — GET /api/v1/notices, POST, PUT, DELETE archive."""
from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, or_, select

from app.dependencies import DbSession, OrganizerAuth
from app.models.category import Category
from app.models.notice import Notice
from app.services.audit import log_operation
from schemas.notice import (
    CreateNoticeRequest,
    NoticeListResponse,
    NoticeResponse,
    StatusResponse,
    UpdateNoticeRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _active_filter(stmt, today: date):
    """Apply archived=false + schedule window filters to a select statement."""
    stmt = stmt.where(Notice.archived.is_(False))
    # start_date: null means always visible from the past; otherwise must be <= today
    stmt = stmt.where(
        or_(Notice.start_date.is_(None), Notice.start_date <= today)
    )
    # end_date: null means no expiry; otherwise must be >= today
    stmt = stmt.where(
        or_(Notice.end_date.is_(None), Notice.end_date >= today)
    )
    return stmt


@router.get("", response_model=NoticeListResponse)
def list_notices(
    db: DbSession,
    category_id: int | None = Query(default=None),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
) -> NoticeListResponse:
    """Return active (non-archived, in-window) notices with optional filtering."""
    today = date.today()
    base = select(Notice)
    base = _active_filter(base, today)

    if category_id is not None:
        base = base.where(Notice.category_id == category_id)

    if search:
        term = f"%{search.lower()}%"
        base = base.where(
            or_(
                func.lower(Notice.title).like(term),
                func.lower(Notice.body).like(term),
            )
        )

    total_stmt = select(func.count()).select_from(base.subquery())
    total: int = db.scalar(total_stmt) or 0

    offset = (page - 1) * limit
    rows = db.scalars(base.order_by(Notice.created_at.desc()).offset(offset).limit(limit)).all()

    pages = max(1, (total + limit - 1) // limit)
    return NoticeListResponse(
        items=list(rows),
        total=total,
        page=page,
        limit=limit,
        pages=pages,
    )


@router.post("", response_model=NoticeResponse, status_code=status.HTTP_201_CREATED)
def create_notice(
    db: DbSession,
    body: CreateNoticeRequest,
    _auth: OrganizerAuth,
) -> NoticeResponse:
    """Create a new notice. Requires organizer secret."""
    if body.category_id is not None:
        cat = db.get(Category, body.category_id)
        if cat is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Category {body.category_id} does not exist",
            )

    notice = Notice(
        title=body.title,
        body=body.body,
        category_id=body.category_id,
        author_display_name=body.author_display_name,
        start_date=body.start_date,
        end_date=body.end_date,
        archived=False,
    )
    db.add(notice)
    db.flush()
    log_operation(db, "notices", "CREATE", notice.id)
    db.commit()
    db.refresh(notice)
    logger.info("notice_created id=%s author=%s", notice.id, notice.author_display_name)
    return notice  # type: ignore[return-value]


@router.put("/{notice_id}", response_model=NoticeResponse)
def update_notice(
    notice_id: int,
    db: DbSession,
    body: UpdateNoticeRequest,
    _auth: OrganizerAuth,
) -> NoticeResponse:
    """Update notice fields. Requires organizer secret."""
    notice = db.get(Notice, notice_id)
    if notice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notice not found")

    updates = body.model_dump(exclude_unset=True)

    if "category_id" in updates and updates["category_id"] is not None:
        cat = db.get(Category, updates["category_id"])
        if cat is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Category {updates['category_id']} does not exist",
            )

    for k, v in updates.items():
        setattr(notice, k, v)

    db.flush()
    log_operation(db, "notices", "UPDATE", notice.id)
    db.commit()
    db.refresh(notice)
    logger.info("notice_updated id=%s", notice.id)
    return notice  # type: ignore[return-value]


@router.delete(
    "/{notice_id}/archive",
    response_model=StatusResponse,
    status_code=status.HTTP_200_OK,
)
def archive_notice(
    notice_id: int,
    db: DbSession,
    _auth: OrganizerAuth,
) -> StatusResponse:
    """Archive a notice (sets archived=true). Requires organizer secret."""
    notice = db.get(Notice, notice_id)
    if notice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notice not found")

    notice.archived = True
    db.flush()
    log_operation(db, "notices", "ARCHIVE", notice.id)
    db.commit()
    logger.info("notice_archived id=%s", notice.id)
    return StatusResponse(status="ok", message=f"Notice {notice_id} archived successfully")
