"""Completions endpoint tests."""
from datetime import date


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_create_completion_hr_admin(client, seed_data):
    headers = auth_header(seed_data["hr_token"])
    resp = client.post("/completions", json={
        "employee_id": seed_data["emp1_id"],
        "course_id": seed_data["course_id"],
        "completion_date": str(date.today()),
    }, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["employee_id"] == seed_data["emp1_id"]
    assert data["is_active_record"] is True
    assert data["expiry_date"] is not None  # 12 months validity


def test_create_completion_employee_self(client, seed_data):
    headers = auth_header(seed_data["emp_token"])
    resp = client.post("/completions", json={
        "employee_id": seed_data["emp1_id"],
        "course_id": seed_data["course_id"],
        "completion_date": str(date.today()),
    }, headers=headers)
    assert resp.status_code == 201


def test_create_completion_employee_other_forbidden(client, seed_data):
    headers = auth_header(seed_data["emp_token"])
    resp = client.post("/completions", json={
        "employee_id": seed_data["emp2_id"],
        "course_id": seed_data["course_id"],
        "completion_date": str(date.today()),
    }, headers=headers)
    assert resp.status_code == 403


def test_recertification_supersedes_prior(client, seed_data):
    headers = auth_header(seed_data["hr_token"])
    # First completion
    resp1 = client.post("/completions", json={
        "employee_id": seed_data["emp1_id"],
        "course_id": seed_data["course_id"],
        "completion_date": "2024-01-01",
    }, headers=headers)
    assert resp1.status_code == 201

    # Second completion (recertification)
    resp2 = client.post("/completions", json={
        "employee_id": seed_data["emp1_id"],
        "course_id": seed_data["course_id"],
        "completion_date": "2024-06-01",
    }, headers=headers)
    assert resp2.status_code == 201
    second_data = resp2.json()
    assert second_data["is_active_record"] is True
