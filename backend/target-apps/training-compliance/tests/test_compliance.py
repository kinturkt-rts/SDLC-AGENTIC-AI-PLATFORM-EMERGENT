"""Compliance endpoint tests."""


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_employee_compliance_view(client, seed_data):
    headers = auth_header(seed_data["hr_token"])
    resp = client.get(f"/compliance/employee/{seed_data['emp1_id']}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    # Should have at least 1 course status (Safety 101 is all-staff + role-required)
    assert len(data) >= 1
    assert data[0]["status"] in ("current", "expired", "missing")


def test_employee_compliance_employee_self(client, seed_data):
    headers = auth_header(seed_data["emp_token"])
    resp = client.get(f"/compliance/employee/{seed_data['emp1_id']}", headers=headers)
    assert resp.status_code == 200


def test_employee_compliance_employee_other_forbidden(client, seed_data):
    headers = auth_header(seed_data["emp_token"])
    resp = client.get(f"/compliance/employee/{seed_data['emp2_id']}", headers=headers)
    assert resp.status_code == 403


def test_team_compliance_manager(client, seed_data):
    headers = auth_header(seed_data["mgr_token"])
    resp = client.get("/compliance/team", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    # Manager should see their direct reports
    assert len(data) >= 1


def test_team_compliance_employee_forbidden(client, seed_data):
    headers = auth_header(seed_data["emp_token"])
    resp = client.get("/compliance/team", headers=headers)
    assert resp.status_code == 403
