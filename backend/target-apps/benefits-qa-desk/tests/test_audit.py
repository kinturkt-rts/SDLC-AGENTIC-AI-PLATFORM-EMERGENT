"""Audit endpoint tests."""
import uuid

from app.models.audit_event import AuditEvent


def test_audit_admin_can_list(client, admin_headers, db_session, seed_users):
    # Insert a sample audit event
    evt = AuditEvent(
        id=str(uuid.uuid4()),
        user_id=seed_users["admin_id"],
        role_at_time="admin",
        action_type="upload",
        resource_type="document",
        resource_id=str(uuid.uuid4()),
        resource_name="test.pdf",
        outcome="success",
    )
    db_session.add(evt)
    db_session.commit()

    resp = client.get("/api/v1/audit", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1


def test_audit_employee_forbidden(client, employee_headers, seed_users):
    resp = client.get("/api/v1/audit", headers=employee_headers)
    assert resp.status_code == 403


def test_audit_contributor_forbidden(client, contributor_headers, seed_users):
    resp = client.get("/api/v1/audit", headers=contributor_headers)
    assert resp.status_code == 403
