"""Audit trail service."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.audit_event import AuditEvent


def log_audit_event(
    db: Session,
    user_id: str,
    role: str,
    action_type: str,
    resource_type: str,
    resource_id: str | None = None,
    resource_name: str | None = None,
    outcome: str = "success",
    question_excerpt: str | None = None,
) -> None:
    """Record an audit event. Call in a finally-guard or after main action."""
    event = AuditEvent(
        user_id=user_id,
        role_at_time=role,
        action_type=action_type,
        resource_type=resource_type,
        resource_id=resource_id,
        resource_name=resource_name,
        outcome=outcome,
        question_excerpt=question_excerpt[:100] if question_excerpt else None,
    )
    db.add(event)
    db.commit()
