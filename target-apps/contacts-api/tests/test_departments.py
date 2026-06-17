"""Tests for /departments routes."""
import pytest


# ── POST /departments ────────────────────────────────────────────────────────


def test_create_department_success(client, api_headers):
    resp = client.post(
        "/departments",
        json={"name": "Finance", "code": "FIN"},
        headers=api_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Finance"
    assert data["code"] == "FIN"
    assert "id" in data
    assert "created_at" in data


def test_create_department_duplicate_code(client, api_headers):
    client.post("/departments", json={"name": "A", "code": "DUP"}, headers=api_headers)
    resp = client.post("/departments", json={"name": "B", "code": "DUP"}, headers=api_headers)
    assert resp.status_code == 409


def test_create_department_no_api_key(client):
    resp = client.post("/departments", json={"name": "X", "code": "XX"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid or missing API key"


def test_create_department_wrong_api_key(client):
    resp = client.post(
        "/departments",
        json={"name": "X", "code": "XX"},
        headers={"X-API-Key": "wrong-key"},
    )
    assert resp.status_code == 401


def test_create_department_code_uppercased(client, api_headers):
    resp = client.post(
        "/departments",
        json={"name": "Lowercase Test", "code": "low"},
        headers=api_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["code"] == "LOW"


# ── GET /departments ─────────────────────────────────────────────────────────


def test_list_departments_empty(client):
    resp = client.get("/departments")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_departments_sorted_by_name(client, api_headers):
    client.post("/departments", json={"name": "Zulu", "code": "ZUL"}, headers=api_headers)
    client.post("/departments", json={"name": "Alpha", "code": "ALP"}, headers=api_headers)
    resp = client.get("/departments")
    assert resp.status_code == 200
    names = [d["name"] for d in resp.json()]
    assert names == ["Alpha", "Zulu"]


# ── GET /departments/{id} ────────────────────────────────────────────────────


def test_get_department_with_contact_count(client, api_headers):
    dept_resp = client.post(
        "/departments", json={"name": "Engineering", "code": "ENG"}, headers=api_headers
    )
    dept_id = dept_resp.json()["id"]

    # Create a contact in that department
    client.post(
        "/contacts",
        json={
            "full_name": "Alice",
            "email": "alice@test.com",
            "department_id": dept_id,
        },
        headers=api_headers,
    )

    resp = client.get(f"/departments/{dept_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["contact_count"] == 1


def test_get_department_not_found(client):
    resp = client.get("/departments/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


# ── PATCH /departments/{id} ──────────────────────────────────────────────────


def test_update_department_name(client, api_headers):
    dept_resp = client.post(
        "/departments", json={"name": "Old Name", "code": "OLD"}, headers=api_headers
    )
    dept_id = dept_resp.json()["id"]

    resp = client.patch(
        f"/departments/{dept_id}",
        json={"name": "New Name"},
        headers=api_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"
    assert resp.json()["code"] == "OLD"


def test_update_department_code_conflict(client, api_headers):
    client.post("/departments", json={"name": "A", "code": "AAA"}, headers=api_headers)
    dept2 = client.post(
        "/departments", json={"name": "B", "code": "BBB"}, headers=api_headers
    )
    dept2_id = dept2.json()["id"]

    resp = client.patch(
        f"/departments/{dept2_id}",
        json={"code": "AAA"},
        headers=api_headers,
    )
    assert resp.status_code == 409


def test_update_department_not_found(client, api_headers):
    resp = client.patch(
        "/departments/00000000-0000-0000-0000-000000000000",
        json={"name": "X"},
        headers=api_headers,
    )
    assert resp.status_code == 404


def test_update_department_requires_api_key(client):
    resp = client.patch(
        "/departments/00000000-0000-0000-0000-000000000000",
        json={"name": "X"},
    )
    assert resp.status_code == 401
