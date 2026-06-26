"""Alerts endpoint tests."""


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_alerts_compliance_officer(client, seed_data):
    headers = auth_header(seed_data["co_token"])
    resp = client.get("/alerts", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_alerts_manager_scoped(client, seed_data):
    headers = auth_header(seed_data["mgr_token"])
    resp = client.get("/alerts", headers=headers)
    assert resp.status_code == 200


def test_alerts_employee_forbidden(client, seed_data):
    headers = auth_header(seed_data["emp_token"])
    resp = client.get("/alerts", headers=headers)
    assert resp.status_code == 403


def test_alerts_type_filter(client, seed_data):
    headers = auth_header(seed_data["co_token"])
    resp = client.get("/alerts?type=overdue", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    for alert in data:
        assert alert["type"] == "overdue"
