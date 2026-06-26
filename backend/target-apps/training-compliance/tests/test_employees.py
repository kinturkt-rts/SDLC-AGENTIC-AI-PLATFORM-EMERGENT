"""Employees endpoint tests."""


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_create_employee(client, seed_data):
    headers = auth_header(seed_data["hr_token"])
    resp = client.post("/employees", json={
        "full_name": "New Person",
        "email": "new@example.com",
        "department_id": seed_data["dept_id"],
        "job_role_id": seed_data["role_id"],
    }, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["full_name"] == "New Person"
    assert data["is_active"] is True


def test_create_employee_forbidden_for_manager(client, seed_data):
    headers = auth_header(seed_data["mgr_token"])
    resp = client.post("/employees", json={
        "full_name": "Nope",
        "email": "nope@example.com",
        "department_id": seed_data["dept_id"],
        "job_role_id": seed_data["role_id"],
    }, headers=headers)
    assert resp.status_code == 403


def test_list_employees(client, seed_data):
    headers = auth_header(seed_data["hr_token"])
    resp = client.get("/employees", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 2


def test_soft_deactivate_employee(client, seed_data):
    headers = auth_header(seed_data["hr_token"])
    resp = client.patch(f"/employees/{seed_data['emp2_id']}", json={
        "is_active": False,
    }, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False
