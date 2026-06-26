"""Audit logging helper — records organizer operations."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def log_operation(
    db: Session,
    table_name: str,
    operation: str,
    record_id: int,
    organizer_action: bool = True,
) -> None:
    """Append one row to audit_log. Flush but do not commit (caller owns the transaction)."""
    entry = AuditLog(
        table_name=table_name,
        operation=operation,
        record_id=record_id,
        organizer_action=organizer_action,
    )
    db.add(entry)
    db.flush()
