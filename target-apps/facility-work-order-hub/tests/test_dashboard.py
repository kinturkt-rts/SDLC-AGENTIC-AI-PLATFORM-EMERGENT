"""Test dashboard endpoints."""
import uuid
from datetime import datetime, timedelta, timezone

from app.models.work_order import WorkOrder


def test_sla_dashboard_leadership(client, seed_users, seed_site, auth_headers, db_session):
    # Create some work orders
    now = datetime.now(timezone.utc)
    wo1 = WorkOrder(
        id=str(uuid.uuid4()),
        title="Open WO",
        description="d",
        category="HVAC",
        priority="normal",
        status="submitted",
        requester_id=seed_users["requester"]["id"],
        site_id=seed_site["id"],
        created_at=now - timedelta(days=5),
        updated_at=now,
    )
    wo2 = WorkOrder(
        id=str(uuid.uuid4()),
        title="Closed WO",
        description="d",
        category="plumbing",
        priority="low",
        status="closed",
        requester_id=seed_users["requester"]["id"],
        site_id=seed_site["id"],
        created_at=now - timedelta(days=10),
        updated_at=now,
        closed_at=now - timedelta(days=1),
    )
    db_session.add_all([wo1, wo2])
    db_session.commit()

    headers = auth_headers("leadership")
    resp = client.get("/api/v1/dashboard/sla", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "open_count" in data
    assert "closed_count" in data
    assert "overdue_count" in data
    assert "avg_days_to_close_by_category" in data
    assert "top_sites" in data


def test_sla_dashboard_forbidden_for_requester(client, seed_users, auth_headers):
    headers = auth_headers("requester")
    resp = client.get("/api/v1/dashboard/sla", headers=headers)
    assert resp.status_code == 403


def test_workload_dashboard_admin(client, seed_users, seed_site, auth_headers, db_session):
    now = datetime.now(timezone.utc)
    wo = WorkOrder(
        id=str(uuid.uuid4()),
        title="Assigned WO",
        description="d",
        category="general",
        priority="normal",
        status="assigned",
        requester_id=seed_users["requester"]["id"],
        assignee_id=seed_users["technician"]["id"],
        site_id=seed_site["id"],
        created_at=now - timedelta(days=2),
        updated_at=now,
        assigned_at=now,
    )
    db_session.add(wo)
    db_session.commit()

    headers = auth_headers("facilities_admin")
    resp = client.get("/api/v1/dashboard/workload", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["open_count"] >= 1


def test_workload_forbidden_for_technician(client, seed_users, auth_headers):
    headers = auth_headers("technician")
    resp = client.get("/api/v1/dashboard/workload", headers=headers)
    assert resp.status_code == 403
