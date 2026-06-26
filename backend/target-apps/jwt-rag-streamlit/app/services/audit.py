from sqlalchemy.orm import Session
from app.models.audit import AuditLog
from typing import Optional, Dict, Any


def log_audit_event(
    db: Session,
    user_id: Optional[int],
    action: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[int] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None
) -> AuditLog:
    """Log an audit event"""
    audit_entry = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address
    )
    
    db.add(audit_entry)
    db.commit()
    
    return audit_entry
