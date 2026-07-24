"""Audit trail service — append-only insert to audit_log."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def write_audit(
    db: Session,
    *,
    expense_id: str,
    actor_id: str,
    actor_role: str,
    action: str,
    from_status: str | None = None,
    to_status: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditLog:
    """Insert a single audit log entry."""
    entry = AuditLog(
        expense_id=expense_id,
        actor_id=actor_id,
        actor_role=actor_role,
        action=action,
        from_status=from_status,
        to_status=to_status,
        metadata_json=metadata,
    )
    db.add(entry)
    return entry
