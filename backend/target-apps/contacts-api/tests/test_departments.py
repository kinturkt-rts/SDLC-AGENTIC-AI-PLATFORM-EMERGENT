"""Department route tests."""
import uuid


def test_list_departments_empty(client):
    """GET /api/v1/departments returns empty list when no data."""
    resp = client.get("/api/v1/departments")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_department_no_key(client):
    """POST without API key returns 401."""
    resp = client.post("/api/v1/departments", json={"name": "Test", "code": "TST"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid or missing API key"


def test_create_department(client, api_headers):
    """POST with API key creates department."""
    resp = client.post(
        "/api/v1/departments",
        json={"name": "Engineering", "code": "ENG"},
        headers=api_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Engineering"
    assert data["code"] == "ENG"
    assert "id" in data
    assert "created_at" in data


def test_create_department_duplicate_code(client, api_headers, sample_department):
    """POST with duplicate code returns 409."""
    resp = client.post(
        "/api/v1/departments",
        json={"name": "Duplicate", "code": sample_department.code},
        headers=api_headers,
    )
    assert resp.status_code == 409


def test_get_department(client, sample_department):
    """GET /departments/{id} returns department with contact_count."""
    resp = client.get(f"/api/v1/departments/{sample_department.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == sample_department.id
    assert data["name"] == sample_department.name
    assert data["contact_count"] == 0


def test_get_department_not_found(client):
    """GET non-existent department returns 404."""
    resp = client.get(f"/api/v1/departments/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_get_department_contact_count(client, sample_contact):
    """contact_count includes contacts in the department."""
    resp = client.get(f"/api/v1/departments/{sample_contact.department_id}")
    assert resp.status_code == 200
    assert resp.json()["contact_count"] == 1


def test_list_departments_sorted(client, api_headers):
    """Departments are sorted by name ascending."""
    client.post("/api/v1/departments", json={"name": "Zebra", "code": "ZEB"}, headers=api_headers)
    client.post("/api/v1/departments", json={"name": "Alpha", "code": "ALP"}, headers=api_headers)
    resp = client.get("/api/v1/departments")
    names = [d["name"] for d in resp.json()]
    assert names == sorted(names)


def test_patch_department(client, api_headers, sample_department):
    """PATCH updates department fields."""
    resp = client.patch(
        f"/api/v1/departments/{sample_department.id}",
        json={"name": "Eng Updated"},
        headers=api_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Eng Updated"
    assert resp.json()["code"] == sample_department.code


def test_patch_department_no_key(client, sample_department):
    """PATCH without API key returns 401."""
    resp = client.patch(
        f"/api/v1/departments/{sample_department.id}",
        json={"name": "Unauthorized"},
    )
    assert resp.status_code == 401
