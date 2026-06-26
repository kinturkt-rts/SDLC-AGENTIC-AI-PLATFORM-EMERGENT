"""Requirements endpoint tests."""


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_list_requirements(client, seed_data):
    headers = auth_header(seed_data["hr_token"])
    resp = client.get("/requirements", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_create_requirement_duplicate_409(client, seed_data):
    headers = auth_header(seed_data["hr_token"])
    resp = client.post("/requirements", json={
        "job_role_id": seed_data["role_id"],
        "course_id": seed_data["course_id"],
    }, headers=headers)
    assert resp.status_code == 409


def test_delete_requirement(client, seed_data):
    headers = auth_header(seed_data["hr_token"])
    resp = client.delete(f"/requirements/{seed_data['req_id']}", headers=headers)
    assert resp.status_code == 204


def test_create_requirement_forbidden_for_employee(client, seed_data):
    headers = auth_header(seed_data["emp_token"])
    resp = client.post("/requirements", json={
        "job_role_id": seed_data["role_id"],
        "course_id": seed_data["course_id"],
    }, headers=headers)
    assert resp.status_code == 403
