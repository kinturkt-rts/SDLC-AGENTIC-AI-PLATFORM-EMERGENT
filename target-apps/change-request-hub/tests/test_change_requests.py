"""Change request tests."""
from datetime import datetime, timedelta, timezone


def _future(days=5):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def test_create_change_request(client, requester_headers, sample_service, sample_environment):
    body = {
        "title": "Test CR",
        "description": "A test change",
        "service_id": sample_service,
        "target_environment_id": sample_environment,
        "change_type": "standard",
        "risk": "low",
        "planned_start": _future(5),
        "planned_end": _future(6),
        "rollback_plan": "Revert git commit",
    }
    resp = client.post("/api/v1/change-requests", json=body, headers=requester_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "draft"
    assert data["title"] == "Test CR"


def test_create_cr_implementer_forbidden(client, implementer_headers, sample_service, sample_environment):
    body = {
        "title": "X",
        "description": "X",
        "service_id": sample_service,
        "target_environment_id": sample_environment,
        "change_type": "standard",
        "risk": "low",
        "planned_start": _future(5),
        "planned_end": _future(6),
        "rollback_plan": "Plan",
    }
    resp = client.post("/api/v1/change-requests", json=body, headers=implementer_headers)
    assert resp.status_code == 403


def test_list_change_requests_role_scoped(client, requester_headers, manager_headers, sample_service, sample_environment):
    body = {
        "title": "Scoped CR",
        "description": "X",
        "service_id": sample_service,
        "target_environment_id": sample_environment,
        "change_type": "normal",
        "risk": "medium",
        "planned_start": _future(5),
        "planned_end": _future(6),
        "rollback_plan": "Plan",
    }
    client.post("/api/v1/change-requests", json=body, headers=requester_headers)
    # Requester sees own
    resp = client.get("/api/v1/change-requests", headers=requester_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1
    # Manager sees all
    resp2 = client.get("/api/v1/change-requests", headers=manager_headers)
    assert resp2.status_code == 200
    assert resp2.json()["total"] >= 1


def test_get_change_request_detail(client, requester_headers, sample_service, sample_environment):
    body = {
        "title": "Detail CR",
        "description": "X",
        "service_id": sample_service,
        "target_environment_id": sample_environment,
        "change_type": "standard",
        "risk": "low",
        "planned_start": _future(5),
        "planned_end": _future(6),
        "rollback_plan": "Plan",
    }
    r = client.post("/api/v1/change-requests", json=body, headers=requester_headers)
    cr_id = r.json()["id"]
    resp = client.get(f"/api/v1/change-requests/{cr_id}", headers=requester_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "approval_records" in data
    assert "status_history" in data


def test_status_transition_submit(client, requester_headers, sample_service, sample_environment):
    body = {
        "title": "Submit CR",
        "description": "X",
        "service_id": sample_service,
        "target_environment_id": sample_environment,
        "change_type": "standard",
        "risk": "low",
        "planned_start": _future(5),
        "planned_end": _future(6),
        "rollback_plan": "Plan",
    }
    r = client.post("/api/v1/change-requests", json=body, headers=requester_headers)
    cr_id = r.json()["id"]
    resp = client.patch(f"/api/v1/change-requests/{cr_id}/status", json={"to_status": "submitted"}, headers=requester_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "submitted"


def test_invalid_transition_returns_422(client, requester_headers, sample_service, sample_environment):
    body = {
        "title": "Invalid",
        "description": "X",
        "service_id": sample_service,
        "target_environment_id": sample_environment,
        "change_type": "standard",
        "risk": "low",
        "planned_start": _future(5),
        "planned_end": _future(6),
        "rollback_plan": "Plan",
    }
    r = client.post("/api/v1/change-requests", json=body, headers=requester_headers)
    cr_id = r.json()["id"]
    # draft -> completed is invalid
    resp = client.patch(f"/api/v1/change-requests/{cr_id}/status", json={"to_status": "completed"}, headers=requester_headers)
    assert resp.status_code == 422
