"""Blackout window tests."""


def test_create_blackout_window_manager(client, manager_headers, sample_environment):
    body = {
        "environment_id": sample_environment,
        "start_at": "2025-08-01T00:00:00+00:00",
        "end_at": "2025-08-07T23:59:59+00:00",
        "reason": "Code freeze",
    }
    resp = client.post("/api/v1/blackout-windows", json=body, headers=manager_headers)
    assert resp.status_code == 201
    assert resp.json()["reason"] == "Code freeze"


def test_create_blackout_window_requester_forbidden(client, requester_headers, sample_environment):
    body = {
        "environment_id": sample_environment,
        "start_at": "2025-08-01T00:00:00+00:00",
        "end_at": "2025-08-07T23:59:59+00:00",
        "reason": "Freeze",
    }
    resp = client.post("/api/v1/blackout-windows", json=body, headers=requester_headers)
    assert resp.status_code == 403


def test_list_blackout_windows(client, manager_headers, sample_environment):
    body = {
        "environment_id": sample_environment,
        "start_at": "2025-08-01T00:00:00+00:00",
        "end_at": "2025-08-07T23:59:59+00:00",
        "reason": "Freeze",
    }
    client.post("/api/v1/blackout-windows", json=body, headers=manager_headers)
    resp = client.get("/api/v1/blackout-windows", headers=manager_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1
