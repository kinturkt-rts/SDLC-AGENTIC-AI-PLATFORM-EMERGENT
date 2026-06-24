"""Tests for incident touch log."""


def test_create_incident_touch(client, api_headers, active_runbook):
    body = {
        "runbook_id": str(active_runbook.id),
        "ticket_reference": "INC-1234",
        "step_number": 1,
        "notes": "Test notes",
    }
    resp = client.post("/api/v1/incident-touches", json=body, headers=api_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["ticket_reference"] == "INC-1234"
    assert data["role"] == "admin"  # dev key = admin


def test_create_incident_touch_no_ticket(client, api_headers, active_runbook):
    body = {
        "runbook_id": str(active_runbook.id),
        "ticket_reference": "",
    }
    resp = client.post("/api/v1/incident-touches", json=body, headers=api_headers)
    assert resp.status_code == 422


def test_create_incident_touch_runbook_not_found(client, api_headers):
    body = {
        "runbook_id": "00000000-0000-0000-0000-000000000000",
        "ticket_reference": "INC-5555",
    }
    resp = client.post("/api/v1/incident-touches", json=body, headers=api_headers)
    assert resp.status_code == 404
