"""Employees endpoint integration tests."""


def test_assign_team(client, admin_headers, seed_data):
    resp = client.put(
        "/api/v1/employees/1/team",
        json={"team_id": 2},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["team_id"] == 2


def test_assign_team_nonexistent_employee(client, admin_headers, seed_data):
    resp = client.put(
        "/api/v1/employees/999/team",
        json={"team_id": 1},
        headers=admin_headers,
    )
    assert resp.status_code == 404


def test_assign_team_nonexistent_team(client, admin_headers, seed_data):
    resp = client.put(
        "/api/v1/employees/1/team",
        json={"team_id": 999},
        headers=admin_headers,
    )
    assert resp.status_code == 404


def test_non_admin_cannot_assign_team(client, emp_headers, seed_data):
    resp = client.put(
        "/api/v1/employees/1/team",
        json={"team_id": 2},
        headers=emp_headers,
    )
    assert resp.status_code == 403
