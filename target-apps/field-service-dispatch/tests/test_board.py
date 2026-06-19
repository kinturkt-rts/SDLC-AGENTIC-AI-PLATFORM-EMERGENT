"""Tests for board and workload endpoints."""
from datetime import date

import pytest


@pytest.fixture()
def setup_board_data(client, seed_users):
    """Create a customer and several work orders for board tests."""
    # Create customer
    resp = client.post(
        "/customers",
        json={
            "full_name": "Board Customer",
            "phone": "555-333-4444",
            "service_addresses": [
                {"street": "1 Board St", "city": "City", "state": "OH", "postal_code": "43215"}
            ],
        },
        headers=seed_users["dispatcher_headers"],
    )
    customer_id = resp.json()["id"]

    # Create unassigned WO
    client.post(
        "/work-orders",
        json={
            "customer_id": customer_id,
            "description": "Unassigned work",
            "priority": "routine",
            "scheduled_date": str(date.today()),
            "time_window": "morning",
        },
        headers=seed_users["dispatcher_headers"],
    )

    # Create assigned WO
    wo_resp = client.post(
        "/work-orders",
        json={
            "customer_id": customer_id,
            "description": "Assigned work",
            "priority": "routine",
            "scheduled_date": str(date.today()),
            "time_window": "afternoon",
        },
        headers=seed_users["dispatcher_headers"],
    )
    wo_id = wo_resp.json()["id"]
    client.patch(
        f"/work-orders/{wo_id}",
        json={"assigned_technician_id": seed_users["technician_id"]},
        headers=seed_users["dispatcher_headers"],
    )

    return customer_id


def test_board_endpoint(client, seed_users, setup_board_data):
    resp = client.get(
        "/board",
        headers=seed_users["dispatcher_headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "unassigned" in data
    assert "technician_columns" in data
    assert "sla_breaches" in data
    assert len(data["unassigned"]) >= 1


def test_board_unauthenticated(client):
    resp = client.get("/board")
    assert resp.status_code == 401


def test_workload_endpoint(client, seed_users, setup_board_data):
    resp = client.get(
        "/workload",
        headers=seed_users["dispatcher_headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "workload" in data
    assert len(data["workload"]) >= 1
    item = data["workload"][0]
    assert "technician_id" in item
    assert "total_assigned" in item
    assert "sla_breach_flag" in item


def test_workload_technician_forbidden(client, seed_users, setup_board_data):
    resp = client.get(
        "/workload",
        headers=seed_users["technician_headers"],
    )
    assert resp.status_code == 403
