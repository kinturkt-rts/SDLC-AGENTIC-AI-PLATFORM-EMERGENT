"""Assignment endpoint tests."""


def test_create_assignment(client, dispatcher_headers, seed_data):
    resp = client.post("/api/v1/assignments", json={
        "work_order_id": seed_data["wo_new_id"],
        "technician_id": seed_data["tech1_id"]
    }, headers=dispatcher_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["work_order_id"] == seed_data["wo_new_id"]
    assert data["technician_id"] == seed_data["tech1_id"]
    assert data["is_active"] is True


def test_assignment_moves_order_to_assigned(client, dispatcher_headers, seed_data):
    # First assign
    client.post("/api/v1/assignments", json={
        "work_order_id": seed_data["wo_new_id"],
        "technician_id": seed_data["tech2_id"]
    }, headers=dispatcher_headers)
    # Check order status
    resp = client.get("/api/v1/work-orders", headers=dispatcher_headers)
    orders = resp.json()
    wo = next(o for o in orders if o["id"] == seed_data["wo_new_id"])
    assert wo["status"] == "assigned"


def test_reassignment_in_assigned_state(client, dispatcher_headers, seed_data):
    wo_id = seed_data["wo_assigned_id"]
    resp = client.post("/api/v1/assignments", json={
        "work_order_id": wo_id,
        "technician_id": seed_data["tech2_id"]
    }, headers=dispatcher_headers)
    assert resp.status_code == 201
    assert resp.json()["technician_id"] == seed_data["tech2_id"]


def test_cannot_assign_inactive_technician(client, dispatcher_headers, seed_data):
    resp = client.post("/api/v1/assignments", json={
        "work_order_id": seed_data["wo_new_id"],
        "technician_id": seed_data["tech_inactive_id"]
    }, headers=dispatcher_headers)
    assert resp.status_code == 422
    assert "inactive" in resp.json()["detail"].lower()


def test_cannot_assign_in_progress_order(client, dispatcher_headers, seed_data):
    resp = client.post("/api/v1/assignments", json={
        "work_order_id": seed_data["wo_in_progress_id"],
        "technician_id": seed_data["tech2_id"]
    }, headers=dispatcher_headers)
    assert resp.status_code == 422


def test_technician_cannot_assign(client, tech_headers, seed_data):
    resp = client.post("/api/v1/assignments", json={
        "work_order_id": seed_data["wo_new_id"],
        "technician_id": seed_data["tech1_id"]
    }, headers=tech_headers)
    assert resp.status_code == 403
