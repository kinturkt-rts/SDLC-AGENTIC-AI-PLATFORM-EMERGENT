"""Tests for work order endpoints."""
import pytest
from datetime import date


@pytest.fixture()
def setup_customer(client, seed_users):
    """Create a customer to use with work orders."""
    resp = client.post(
        "/customers",
        json={
            "full_name": "WO Customer",
            "phone": "555-111-2222",
            "service_addresses": [
                {"street": "1 Test St", "city": "City", "state": "OH", "postal_code": "43215"}
            ],
        },
        headers=seed_users["dispatcher_headers"],
    )
    return resp.json()["id"]


def test_create_work_order(client, seed_users, setup_customer):
    resp = client.post(
        "/work-orders",
        json={
            "customer_id": setup_customer,
            "description": "Fix the AC",
            "priority": "urgent",
            "scheduled_date": str(date.today()),
            "time_window": "morning",
        },
        headers=seed_users["dispatcher_headers"],
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "new"
    assert data["priority"] == "urgent"


def test_create_work_order_owner_forbidden(client, seed_users, setup_customer):
    resp = client.post(
        "/work-orders",
        json={
            "customer_id": setup_customer,
            "description": "Test",
            "priority": "routine",
            "scheduled_date": str(date.today()),
            "time_window": "all_day",
        },
        headers=seed_users["owner_headers"],
    )
    assert resp.status_code == 403


def test_assign_work_order(client, seed_users, setup_customer):
    # Create a work order
    create_resp = client.post(
        "/work-orders",
        json={
            "customer_id": setup_customer,
            "description": "Assign test",
            "priority": "routine",
            "scheduled_date": str(date.today()),
            "time_window": "morning",
        },
        headers=seed_users["dispatcher_headers"],
    )
    wo_id = create_resp.json()["id"]

    # Assign
    resp = client.patch(
        f"/work-orders/{wo_id}",
        json={"assigned_technician_id": seed_users["technician_id"]},
        headers=seed_users["dispatcher_headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "assigned"
    assert resp.json()["assigned_technician_id"] == seed_users["technician_id"]


def test_assign_inactive_tech_rejected(client, seed_users, setup_customer):
    create_resp = client.post(
        "/work-orders",
        json={
            "customer_id": setup_customer,
            "description": "Inactive tech test",
            "priority": "routine",
            "scheduled_date": str(date.today()),
            "time_window": "afternoon",
        },
        headers=seed_users["dispatcher_headers"],
    )
    wo_id = create_resp.json()["id"]

    resp = client.patch(
        f"/work-orders/{wo_id}",
        json={"assigned_technician_id": "a1000000-0000-0000-0000-000000000099"},
        headers=seed_users["dispatcher_headers"],
    )
    assert resp.status_code == 422
    assert "not active" in resp.json()["detail"]


def test_technician_start_job(client, seed_users, setup_customer):
    # Create and assign
    create_resp = client.post(
        "/work-orders",
        json={
            "customer_id": setup_customer,
            "description": "Tech start test",
            "priority": "routine",
            "scheduled_date": str(date.today()),
            "time_window": "morning",
        },
        headers=seed_users["dispatcher_headers"],
    )
    wo_id = create_resp.json()["id"]
    client.patch(
        f"/work-orders/{wo_id}",
        json={"assigned_technician_id": seed_users["technician_id"]},
        headers=seed_users["dispatcher_headers"],
    )

    # Technician starts
    resp = client.patch(
        f"/work-orders/{wo_id}",
        json={"status": "in_progress"},
        headers=seed_users["technician_headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"


def test_technician_complete_without_notes_rejected(client, seed_users, setup_customer):
    # Create, assign, start
    create_resp = client.post(
        "/work-orders",
        json={
            "customer_id": setup_customer,
            "description": "Complete no notes",
            "priority": "routine",
            "scheduled_date": str(date.today()),
            "time_window": "all_day",
        },
        headers=seed_users["dispatcher_headers"],
    )
    wo_id = create_resp.json()["id"]
    client.patch(
        f"/work-orders/{wo_id}",
        json={"assigned_technician_id": seed_users["technician_id"]},
        headers=seed_users["dispatcher_headers"],
    )
    client.patch(
        f"/work-orders/{wo_id}",
        json={"status": "in_progress"},
        headers=seed_users["technician_headers"],
    )

    # Complete without notes
    resp = client.patch(
        f"/work-orders/{wo_id}",
        json={"status": "completed"},
        headers=seed_users["technician_headers"],
    )
    assert resp.status_code == 422
    assert "Completion notes are required" in resp.json()["detail"]


def test_technician_complete_with_notes_and_parts(client, seed_users, setup_customer):
    create_resp = client.post(
        "/work-orders",
        json={
            "customer_id": setup_customer,
            "description": "Complete with parts",
            "priority": "routine",
            "scheduled_date": str(date.today()),
            "time_window": "morning",
        },
        headers=seed_users["dispatcher_headers"],
    )
    wo_id = create_resp.json()["id"]
    client.patch(
        f"/work-orders/{wo_id}",
        json={"assigned_technician_id": seed_users["technician_id"]},
        headers=seed_users["dispatcher_headers"],
    )
    client.patch(
        f"/work-orders/{wo_id}",
        json={"status": "in_progress"},
        headers=seed_users["technician_headers"],
    )

    resp = client.patch(
        f"/work-orders/{wo_id}",
        json={
            "status": "completed",
            "completion_notes": "Fixed the unit. All good.",
            "parts": [
                {"part_name": "Filter", "quantity": 1, "unit_cost": 12.50},
                {"part_name": "Capacitor", "quantity": 2},
            ],
        },
        headers=seed_users["technician_headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["completion_notes"] == "Fixed the unit. All good."
    assert len(data["parts"]) == 2


def test_completed_order_rejects_status_change(client, seed_users, setup_customer):
    create_resp = client.post(
        "/work-orders",
        json={
            "customer_id": setup_customer,
            "description": "Lock test",
            "priority": "routine",
            "scheduled_date": str(date.today()),
            "time_window": "morning",
        },
        headers=seed_users["dispatcher_headers"],
    )
    wo_id = create_resp.json()["id"]
    client.patch(
        f"/work-orders/{wo_id}",
        json={"assigned_technician_id": seed_users["technician_id"]},
        headers=seed_users["dispatcher_headers"],
    )
    client.patch(
        f"/work-orders/{wo_id}",
        json={"status": "in_progress"},
        headers=seed_users["technician_headers"],
    )
    client.patch(
        f"/work-orders/{wo_id}",
        json={"status": "completed", "completion_notes": "Done"},
        headers=seed_users["technician_headers"],
    )

    # Try to cancel
    resp = client.patch(
        f"/work-orders/{wo_id}",
        json={"status": "cancelled"},
        headers=seed_users["dispatcher_headers"],
    )
    assert resp.status_code == 409


def test_addendum_on_completed(client, seed_users, setup_customer):
    create_resp = client.post(
        "/work-orders",
        json={
            "customer_id": setup_customer,
            "description": "Addendum test",
            "priority": "routine",
            "scheduled_date": str(date.today()),
            "time_window": "morning",
        },
        headers=seed_users["dispatcher_headers"],
    )
    wo_id = create_resp.json()["id"]
    client.patch(
        f"/work-orders/{wo_id}",
        json={"assigned_technician_id": seed_users["technician_id"]},
        headers=seed_users["dispatcher_headers"],
    )
    client.patch(
        f"/work-orders/{wo_id}",
        json={"status": "in_progress"},
        headers=seed_users["technician_headers"],
    )
    client.patch(
        f"/work-orders/{wo_id}",
        json={"status": "completed", "completion_notes": "Initial notes"},
        headers=seed_users["technician_headers"],
    )

    # Addendum
    resp = client.patch(
        f"/work-orders/{wo_id}",
        json={"addendum": "Additional info from dispatcher"},
        headers=seed_users["dispatcher_headers"],
    )
    assert resp.status_code == 200
    assert "Additional info from dispatcher" in resp.json()["completion_notes"]


def test_work_order_history(client, seed_users, setup_customer):
    create_resp = client.post(
        "/work-orders",
        json={
            "customer_id": setup_customer,
            "description": "History test",
            "priority": "routine",
            "scheduled_date": str(date.today()),
            "time_window": "afternoon",
        },
        headers=seed_users["dispatcher_headers"],
    )
    wo_id = create_resp.json()["id"]

    # Assign
    client.patch(
        f"/work-orders/{wo_id}",
        json={"assigned_technician_id": seed_users["technician_id"]},
        headers=seed_users["dispatcher_headers"],
    )

    # Get history
    resp = client.get(
        f"/work-orders/{wo_id}/history",
        headers=seed_users["dispatcher_headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    # Should have at least 2 entries: created (new) + assigned
    assert len(data) >= 2


def test_technician_cannot_modify_others_order(client, seed_users, setup_customer, db_session):
    """Technician gets 403 trying to update an order assigned to someone else."""
    from app.models.technician import Technician as TechModel

    other_tech = TechModel(
        id="a1000000-0000-0000-0000-000000000050",
        display_name="Other Tech",
        skills=["commercial"],
        is_active=True,
    )
    db_session.add(other_tech)
    db_session.commit()

    create_resp = client.post(
        "/work-orders",
        json={
            "customer_id": setup_customer,
            "description": "Other tech order",
            "priority": "routine",
            "scheduled_date": str(date.today()),
            "time_window": "morning",
        },
        headers=seed_users["dispatcher_headers"],
    )
    wo_id = create_resp.json()["id"]
    # Assign to other tech
    client.patch(
        f"/work-orders/{wo_id}",
        json={"assigned_technician_id": "a1000000-0000-0000-0000-000000000050"},
        headers=seed_users["dispatcher_headers"],
    )

    # Our technician tries to start it — forbidden
    resp = client.patch(
        f"/work-orders/{wo_id}",
        json={"status": "in_progress"},
        headers=seed_users["technician_headers"],
    )
    assert resp.status_code == 403
