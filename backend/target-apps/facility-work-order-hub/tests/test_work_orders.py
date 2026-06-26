"""Test work order endpoints."""
import uuid
from datetime import datetime, timedelta, timezone

from app.models.site import Site
from app.models.work_order import WorkOrder


def test_create_work_order(client, seed_users, seed_site, auth_headers):
    headers = auth_headers("requester")
    resp = client.post("/api/v1/work-orders", json={
        "title": "Broken pipe",
        "description": "Water leaking",
        "category": "plumbing",
        "priority": "urgent",
        "site_id": seed_site["id"],
    }, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "submitted"
    assert data["title"] == "Broken pipe"
    # Urgent without due_by should produce warning
    assert data["warnings"] is not None
    assert "urgent orders suggest due_by within 24h" in data["warnings"]


def test_create_wo_inactive_site(client, seed_users, auth_headers, db_session):
    inactive_site = Site(
        id=str(uuid.uuid4()),
        site_code="INACTIVE-01",
        name="Inactive",
        address_line="nowhere",
        active=False,
    )
    db_session.add(inactive_site)
    db_session.commit()

    headers = auth_headers("requester")
    resp = client.post("/api/v1/work-orders", json={
        "title": "test",
        "description": "test",
        "category": "general",
        "priority": "low",
        "site_id": inactive_site.id,
    }, headers=headers)
    assert resp.status_code == 422
    assert "inactive" in resp.json()["detail"].lower()


def test_list_work_orders_role_scoping(client, seed_users, seed_site, auth_headers, db_session):
    # Create a WO as requester
    headers = auth_headers("requester")
    client.post("/api/v1/work-orders", json={
        "title": "My order",
        "description": "desc",
        "category": "HVAC",
        "priority": "low",
        "site_id": seed_site["id"],
    }, headers=headers)

    # Requester sees their own
    resp = client.get("/api/v1/work-orders", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1

    # Technician sees nothing (not assigned)
    tech_headers = auth_headers("technician")
    resp2 = client.get("/api/v1/work-orders", headers=tech_headers)
    assert resp2.status_code == 200
    assert resp2.json()["total"] == 0


def test_get_work_order_is_overdue(client, seed_users, seed_site, auth_headers, db_session):
    # Create a WO that is overdue
    wo_id = str(uuid.uuid4())
    wo = WorkOrder(
        id=wo_id,
        title="Overdue order",
        description="past due",
        category="general",
        priority="urgent",
        status="in_progress",
        requester_id=seed_users["requester"]["id"],
        assignee_id=seed_users["technician"]["id"],
        site_id=seed_site["id"],
        due_by=datetime.now(timezone.utc) - timedelta(hours=1),
        created_at=datetime.now(timezone.utc) - timedelta(days=5),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(wo)
    db_session.commit()

    headers = auth_headers("facilities_admin")
    resp = client.get(f"/api/v1/work-orders/{wo_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["is_overdue"] is True


def test_status_transition(client, seed_users, seed_site, auth_headers, db_session):
    # Create a WO and move it through statuses using admin
    headers = auth_headers("facilities_admin")
    resp = client.post("/api/v1/work-orders", json={
        "title": "Transition test",
        "description": "desc",
        "category": "electrical",
        "priority": "normal",
        "site_id": seed_site["id"],
    }, headers=headers)
    wo_id = resp.json()["id"]

    # submitted -> triaged
    resp = client.patch(f"/api/v1/work-orders/{wo_id}/status", json={"status": "triaged"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "triaged"


def test_assign_work_order(client, seed_users, seed_site, auth_headers, db_session):
    headers = auth_headers("facilities_admin")
    # Create WO
    resp = client.post("/api/v1/work-orders", json={
        "title": "Assign test",
        "description": "desc",
        "category": "HVAC",
        "priority": "low",
        "site_id": seed_site["id"],
    }, headers=headers)
    wo_id = resp.json()["id"]

    # Move to triaged
    client.patch(f"/api/v1/work-orders/{wo_id}/status", json={"status": "triaged"}, headers=headers)

    # Assign
    tech_id = seed_users["technician"]["id"]
    resp = client.patch(f"/api/v1/work-orders/{wo_id}/assign", json={"assignee_id": tech_id}, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "assigned"
    assert data["assignee_id"] == tech_id
    assert data["assigned_at"] is not None
