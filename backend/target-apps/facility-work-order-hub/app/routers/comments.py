"""Comments router."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.dependencies import AuthUser, DbSession
from app.models.comment import Comment
from app.models.user import User
from app.models.work_order import WorkOrder
from schemas.comment import CommentCreate, CommentOut

router = APIRouter()


def _check_read_access(wo: WorkOrder, user: AuthUser) -> None:
    """Raise 403 if user cannot read this work order."""
    if user.role in ("facilities_admin", "leadership"):
        return
    if user.role == "requester" and wo.requester_id == user.user_id:
        return
    if user.role == "technician" and wo.assignee_id == user.user_id:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")


@router.post("", response_model=CommentOut, status_code=status.HTTP_201_CREATED)
def create_comment(
    work_order_id: str,
    body: CommentCreate,
    db: DbSession,
    current_user: AuthUser,
) -> CommentOut:
    wo = db.scalars(select(WorkOrder).where(WorkOrder.id == work_order_id)).first()
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
    _check_read_access(wo, current_user)

    if not body.body.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Comment body cannot be empty")

    now = datetime.now(timezone.utc)
    comment = Comment(
        work_order_id=work_order_id,
        author_id=current_user.user_id,
        body=body.body,
        created_at=now,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)

    # Get author display name
    author = db.scalars(select(User).where(User.id == current_user.user_id)).first()
    return CommentOut(
        id=str(comment.id),
        work_order_id=str(comment.work_order_id),
        author_id=str(comment.author_id),
        body=comment.body,
        created_at=comment.created_at,
        author_display_name=author.display_name if author else None,
    )


@router.get("", response_model=list[CommentOut])
def list_comments(
    work_order_id: str,
    db: DbSession,
    current_user: AuthUser,
) -> list[CommentOut]:
    wo = db.scalars(select(WorkOrder).where(WorkOrder.id == work_order_id)).first()
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
    _check_read_access(wo, current_user)

    comments = list(
        db.scalars(
            select(Comment)
            .where(Comment.work_order_id == work_order_id)
            .order_by(Comment.created_at)
        ).all()
    )

    results: list[CommentOut] = []
    for c in comments:
        author = db.scalars(select(User).where(User.id == c.author_id)).first()
        if current_user.role == "leadership":
            # Strip PII for leadership
            results.append(CommentOut(
                id=str(c.id),
                work_order_id=str(c.work_order_id),
                author_id=None,
                body=c.body,
                created_at=c.created_at,
                author_display_name=author.display_name if author else None,
            ))
        else:
            results.append(CommentOut(
                id=str(c.id),
                work_order_id=str(c.work_order_id),
                author_id=str(c.author_id),
                body=c.body,
                created_at=c.created_at,
                author_display_name=author.display_name if author else None,
            ))
    return results
