"""Work order endpoint tests."""
from datetime import date


def test_create_work_order(client, dispatcher_headers, seed_data):
    resp = client.post("/api/v1/work-orders", json={
        "customer_id": seed_data["customer_id"],
        "description": "Test order",
        "priority": "routine",
        "scheduled_date": str(date.today()),
        "time_window": "morning"
    }, headers=dispatcher_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "new"


def test_list_work_orders_dispatcher(client, dispatcher_headers, seed_data):
    resp = client.get("/api/v1/work-orders", headers=dispatcher_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 4


def test_list_work_orders_technician_sees_own(client, tech_headers, seed_data):
    resp = client.get("/api/v1/work-orders", headers=tech_headers)
    assert resp.status_code == 200
    data = resp.json()
    # Technician sees only assigned orders (assigned + in_progress)
    assert len(data) == 2


def test_status_transition_assigned_to_in_progress(client, tech_headers, seed_data):
    wo_id = seed_data["wo_assigned_id"]
    resp = client.patch(f"/api/v1/work-orders/{wo_id}/status", json={
        "status": "in_progress"
    }, headers=tech_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"


def test_status_transition_to_completed_requires_notes(client, tech_headers, seed_data):
    wo_id = seed_data["wo_in_progress_id"]
    resp = client.patch(f"/api/v1/work-orders/{wo_id}/status", json={
        "status": "completed"
    }, headers=tech_headers)
    assert resp.status_code == 422


def test_status_transition_to_completed_with_notes(client, tech_headers, seed_data):
    wo_id = seed_data["wo_in_progress_id"]
    resp = client.patch(f"/api/v1/work-orders/{wo_id}/status", json={
        "status": "completed",
        "completion_notes": "All done.",
        "parts": [{"name": "Filter", "quantity": 1, "unit_cost": 34.99}]
    }, headers=tech_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"
    assert resp.json()["completion_notes"] == "All done."


def test_illegal_transition_returns_409(client, dispatcher_headers, seed_data):
    wo_id = seed_data["wo_new_id"]
    resp = client.patch(f"/api/v1/work-orders/{wo_id}/status", json={
        "status": "completed"
    }, headers=dispatcher_headers)
    assert resp.status_code == 409


def test_terminal_state_returns_422(client, dispatcher_headers, seed_data):
    wo_id = seed_data["wo_completed_id"]
    resp = client.patch(f"/api/v1/work-orders/{wo_id}/status", json={
        "status": "cancelled"
    }, headers=dispatcher_headers)
    assert resp.status_code == 422


def test_owner_cannot_update_status(client, owner_headers, seed_data):
    wo_id = seed_data["wo_new_id"]
    resp = client.patch(f"/api/v1/work-orders/{wo_id}/status", json={
        "status": "cancelled"
    }, headers=owner_headers)
    assert resp.status_code == 403


def test_addendum_on_completed(client, dispatcher_headers, seed_data):
    wo_id = seed_data["wo_completed_id"]
    resp = client.patch(f"/api/v1/work-orders/{wo_id}/addendum", json={
        "dispatcher_addendum": "Follow-up scheduled."
    }, headers=dispatcher_headers)
    assert resp.status_code == 200
    assert resp.json()["dispatcher_addendum"] == "Follow-up scheduled."
