"""Admin router — stats endpoint (staff-only)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_staff
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.models.faq_entry import FaqEntry
from app.models.user import User
from schemas.admin import AdminStats

router = APIRouter()


@router.get("/stats", response_model=AdminStats)
def get_admin_stats(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_staff),
):
    """Return aggregate statistics for the admin dashboard."""
    total_faqs = db.query(FaqEntry).count()
    total_sessions = db.query(ChatSession).count()
    total_messages = db.query(ChatMessage).count()
    fallback_count = db.query(ChatMessage).filter(
        ChatMessage.is_fallback == True  # noqa: E712
    ).count()
    fallback_rate = (fallback_count / total_messages) if total_messages > 0 else 0.0
    return AdminStats(
        total_faqs=total_faqs,
        total_sessions=total_sessions,
        total_messages=total_messages,
        fallback_rate=round(fallback_rate, 4),
    )
