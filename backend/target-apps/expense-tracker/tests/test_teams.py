"""Teams endpoint integration tests."""
from decimal import Decimal


def test_create_team(client, admin_headers):
    resp = client.post("/api/v1/teams", json={"name": "DevOps"}, headers=admin_headers)
    assert resp.status_code == 201
    assert resp.json()["name"] == "DevOps"


def test_create_team_duplicate(client, admin_headers):
    client.post("/api/v1/teams", json={"name": "QA"}, headers=admin_headers)
    resp = client.post("/api/v1/teams", json={"name": "QA"}, headers=admin_headers)
    assert resp.status_code == 409


def test_list_teams(client, admin_headers):
    resp = client.get("/api/v1/teams", headers=admin_headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 2


def test_team_report(client, emp_headers, admin_headers, mgr_headers, seed_data):
    resp = client.post(
        "/api/v1/expenses",
        json={"amount": "200.00", "currency": "EUR", "category": "travel", "expense_date": "2024-06-15"},
        headers=emp_headers,
    )
    expense_id = resp.json()["id"]
    client.post(f"/api/v1/expenses/{expense_id}/approve", headers=admin_headers)

    resp2 = client.get("/api/v1/teams/1/report?year=2024&month=6", headers=mgr_headers)
    assert resp2.status_code == 200
    data = resp2.json()
    assert data["team_id"] == 1
    assert data["year"] == 2024
    assert data["month"] == 6
    assert Decimal(data["grand_total"]) > 0


def test_team_report_forbidden_other_team(client, mgr_headers, seed_data):
    resp = client.get("/api/v1/teams/2/report?year=2024&month=6", headers=mgr_headers)
    assert resp.status_code == 403


def test_non_admin_cannot_create_team(client, emp_headers):
    resp = client.post("/api/v1/teams", json={"name": "Test"}, headers=emp_headers)
    assert resp.status_code == 403
