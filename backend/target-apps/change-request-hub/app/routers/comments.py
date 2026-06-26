"""Comments router — append-only thread on a change request."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.dependencies import AuthUser, DbSession
from app.models.change_request import ChangeRequest
from app.models.comment import Comment
from schemas.comment import CommentCreate, CommentListPage, CommentOut

router = APIRouter()


@router.get("/api/v1/change-requests/{id}/comments", response_model=CommentListPage)
def list_comments(
    id: str,
    db: DbSession,
    current_user: AuthUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> CommentListPage:
    """Get ordered comment thread for a change request."""
    cr = db.scalars(select(ChangeRequest).where(ChangeRequest.id == id)).first()
    if not cr:
        raise HTTPException(status_code=404, detail="Change request not found")

    count_stmt = select(func.count(Comment.id)).where(Comment.change_id == id)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(
        select(Comment)
        .where(Comment.change_id == id)
        .order_by(Comment.posted_at)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return CommentListPage(items=rows, total=total, page=page, page_size=page_size)


@router.post("/api/v1/change-requests/{id}/comments", response_model=CommentOut, status_code=status.HTTP_201_CREATED)
def create_comment(
    id: str,
    body: CommentCreate,
    db: DbSession,
    current_user: AuthUser,
) -> CommentOut:
    """Add a comment to a change request (append-only)."""
    cr = db.scalars(select(ChangeRequest).where(ChangeRequest.id == id)).first()
    if not cr:
        raise HTTPException(status_code=404, detail="Change request not found")

    # Permission: manager=any, requester=own, implementer=assigned
    if current_user.role == "requester" and cr.requester_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Requesters can only comment on own changes")
    if current_user.role == "implementer" and cr.implementer_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Implementers can only comment on assigned changes")
    if current_user.role == "leadership":
        raise HTTPException(status_code=403, detail="Leadership cannot post comments")

    comment = Comment(
        change_id=id,
        author_id=current_user.user_id,
        body=body.body,
        posted_at=datetime.now(timezone.utc),
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment  # type: ignore[return-value]
