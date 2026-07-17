"""Board endpoint tests."""
from datetime import date


def test_board_returns_sections(client, dispatcher_headers, seed_data):
    resp = client.get("/api/v1/board", params={"date": str(date.today())}, headers=dispatcher_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "unassigned" in data
    assert "technicians" in data
    assert "sla_breaches" in data


def test_board_owner_can_access(client, owner_headers, seed_data):
    resp = client.get("/api/v1/board", headers=owner_headers)
    assert resp.status_code == 200


def test_board_technician_forbidden(client, tech_headers, seed_data):
    resp = client.get("/api/v1/board", headers=tech_headers)
    assert resp.status_code == 403


def test_board_unassigned_contains_new_orders(client, dispatcher_headers, seed_data):
    resp = client.get("/api/v1/board", params={"date": str(date.today())}, headers=dispatcher_headers)
    data = resp.json()
    unassigned_ids = [o["id"] for o in data["unassigned"]]
    assert seed_data["wo_new_id"] in unassigned_ids
