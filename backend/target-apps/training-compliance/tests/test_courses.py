"""Courses endpoint tests."""


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_create_course_hr_admin(client, seed_data):
    headers = auth_header(seed_data["hr_token"])
    resp = client.post("/courses", json={
        "name": "New Course",
        "category": "security",
        "validity_period_months": 6,
        "required_for_all_staff": False,
    }, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "New Course"
    assert data["category"] == "security"
    assert data["is_active"] is True


def test_create_course_duplicate_409(client, seed_data):
    headers = auth_header(seed_data["hr_token"])
    resp = client.post("/courses", json={
        "name": "Safety 101",
        "category": "safety",
    }, headers=headers)
    assert resp.status_code == 409


def test_create_course_forbidden_for_employee(client, seed_data):
    headers = auth_header(seed_data["emp_token"])
    resp = client.post("/courses", json={
        "name": "Forbidden Course",
        "category": "safety",
    }, headers=headers)
    assert resp.status_code == 403


def test_list_courses(client, seed_data):
    headers = auth_header(seed_data["hr_token"])
    resp = client.get("/courses", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_get_course(client, seed_data):
    headers = auth_header(seed_data["hr_token"])
    resp = client.get(f"/courses/{seed_data['course_id']}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Safety 101"


def test_patch_course(client, seed_data):
    headers = auth_header(seed_data["hr_token"])
    resp = client.patch(f"/courses/{seed_data['course_id']}", json={
        "certificate_ref": "CERT-001",
    }, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["certificate_ref"] == "CERT-001"
