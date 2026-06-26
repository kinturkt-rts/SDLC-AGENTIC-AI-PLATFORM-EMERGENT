"""Reports dashboard endpoint tests."""


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_dashboard_compliance_officer(client, seed_data):
    headers = auth_header(seed_data["co_token"])
    resp = client.get("/reports/dashboard", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "overdue" in data
    assert "expiring_soon" in data
    assert "rate_by_dept" in data
    assert "course_gaps" in data


def test_dashboard_forbidden_for_employee(client, seed_data):
    headers = auth_header(seed_data["emp_token"])
    resp = client.get("/reports/dashboard", headers=headers)
    assert resp.status_code == 403


def test_dashboard_forbidden_for_manager(client, seed_data):
    headers = auth_header(seed_data["mgr_token"])
    resp = client.get("/reports/dashboard", headers=headers)
    assert resp.status_code == 403
