"""Tests for /contacts routes."""
import pytest


def _create_dept(client, api_headers, name="Test Dept", code="TST"):
    resp = client.post(
        "/departments", json={"name": name, "code": code}, headers=api_headers
    )
    assert resp.status_code == 201
    return resp.json()["id"]


# ── POST /contacts ───────────────────────────────────────────────────────────


def test_create_contact_success(client, api_headers):
    dept_id = _create_dept(client, api_headers)
    resp = client.post(
        "/contacts",
        json={
            "full_name": "Jane Doe",
            "email": "jane@example.com",
            "department_id": dept_id,
            "phone": "+1-555-0100",
            "title": "Manager",
        },
        headers=api_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["full_name"] == "Jane Doe"
    assert data["email"] == "jane@example.com"
    assert data["is_active"] is True
    assert data["department_id"] == dept_id


def test_create_contact_bad_department(client, api_headers):
    resp = client.post(
        "/contacts",
        json={
            "full_name": "X",
            "email": "x@example.com",
            "department_id": "00000000-0000-0000-0000-000000000000",
        },
        headers=api_headers,
    )
    assert resp.status_code == 404


def test_create_contact_duplicate_email(client, api_headers):
    dept_id = _create_dept(client, api_headers)
    client.post(
        "/contacts",
        json={"full_name": "A", "email": "dup@test.com", "department_id": dept_id},
        headers=api_headers,
    )
    resp = client.post(
        "/contacts",
        json={"full_name": "B", "email": "dup@test.com", "department_id": dept_id},
        headers=api_headers,
    )
    assert resp.status_code == 409


def test_create_contact_no_api_key(client):
    resp = client.post(
        "/contacts",
        json={"full_name": "X", "email": "x@t.com", "department_id": "any"},
    )
    assert resp.status_code == 401


# ── GET /contacts (list with pagination, filters, search) ────────────────────


def test_list_contacts_empty(client):
    resp = client.get("/contacts")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["limit"] == 20
    assert data["offset"] == 0


def test_list_contacts_pagination(client, api_headers):
    dept_id = _create_dept(client, api_headers)
    for i in range(5):
        client.post(
            "/contacts",
            json={
                "full_name": f"Person {i}",
                "email": f"p{i}@test.com",
                "department_id": dept_id,
            },
            headers=api_headers,
        )

    resp = client.get("/contacts?limit=2&offset=0")
    data = resp.json()
    assert data["total"] == 5
    assert len(data["items"]) == 2
    assert data["limit"] == 2
    assert data["offset"] == 0


def test_list_contacts_filter_department(client, api_headers):
    dept1 = _create_dept(client, api_headers, "D1", "DDD")
    dept2 = _create_dept(client, api_headers, "D2", "EEE")
    client.post(
        "/contacts",
        json={"full_name": "A", "email": "a@t.com", "department_id": dept1},
        headers=api_headers,
    )
    client.post(
        "/contacts",
        json={"full_name": "B", "email": "b@t.com", "department_id": dept2},
        headers=api_headers,
    )

    resp = client.get(f"/contacts?department_id={dept1}")
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["full_name"] == "A"


def test_list_contacts_filter_is_active(client, api_headers):
    dept_id = _create_dept(client, api_headers)
    create_resp = client.post(
        "/contacts",
        json={"full_name": "Active", "email": "active@t.com", "department_id": dept_id},
        headers=api_headers,
    )
    cid = create_resp.json()["id"]
    # Soft-delete
    client.delete(f"/contacts/{cid}", headers=api_headers)

    resp = client.get("/contacts?is_active=false")
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["is_active"] is False


def test_list_contacts_search_q(client, api_headers):
    dept_id = _create_dept(client, api_headers)
    client.post(
        "/contacts",
        json={"full_name": "Alice Wonder", "email": "aw@t.com", "department_id": dept_id},
        headers=api_headers,
    )
    client.post(
        "/contacts",
        json={"full_name": "Bob Smith", "email": "bob@t.com", "department_id": dept_id},
        headers=api_headers,
    )

    resp = client.get("/contacts?q=alice")
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["full_name"] == "Alice Wonder"


# ── GET /contacts/{id} ───────────────────────────────────────────────────────


def test_get_contact_success(client, api_headers):
    dept_id = _create_dept(client, api_headers)
    create_resp = client.post(
        "/contacts",
        json={"full_name": "Fetch Me", "email": "fetch@t.com", "department_id": dept_id},
        headers=api_headers,
    )
    cid = create_resp.json()["id"]

    resp = client.get(f"/contacts/{cid}")
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Fetch Me"


def test_get_contact_not_found(client):
    resp = client.get("/contacts/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


# ── PATCH /contacts/{id} ─────────────────────────────────────────────────────


def test_update_contact_success(client, api_headers):
    dept_id = _create_dept(client, api_headers)
    create_resp = client.post(
        "/contacts",
        json={"full_name": "Old Name", "email": "old@t.com", "department_id": dept_id},
        headers=api_headers,
    )
    cid = create_resp.json()["id"]

    resp = client.patch(
        f"/contacts/{cid}",
        json={"full_name": "New Name"},
        headers=api_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "New Name"


def test_update_contact_email_conflict(client, api_headers):
    dept_id = _create_dept(client, api_headers)
    client.post(
        "/contacts",
        json={"full_name": "A", "email": "taken@t.com", "department_id": dept_id},
        headers=api_headers,
    )
    c2 = client.post(
        "/contacts",
        json={"full_name": "B", "email": "free@t.com", "department_id": dept_id},
        headers=api_headers,
    )
    cid = c2.json()["id"]

    resp = client.patch(
        f"/contacts/{cid}",
        json={"email": "taken@t.com"},
        headers=api_headers,
    )
    assert resp.status_code == 409


def test_update_contact_not_found(client, api_headers):
    resp = client.patch(
        "/contacts/00000000-0000-0000-0000-000000000000",
        json={"full_name": "X"},
        headers=api_headers,
    )
    assert resp.status_code == 404


def test_update_contact_requires_api_key(client):
    resp = client.patch(
        "/contacts/00000000-0000-0000-0000-000000000000",
        json={"full_name": "X"},
    )
    assert resp.status_code == 401


# ── DELETE /contacts/{id} (soft-delete) ──────────────────────────────────────


def test_soft_delete_contact(client, api_headers):
    dept_id = _create_dept(client, api_headers)
    create_resp = client.post(
        "/contacts",
        json={"full_name": "Deletable", "email": "del@t.com", "department_id": dept_id},
        headers=api_headers,
    )
    cid = create_resp.json()["id"]

    resp = client.delete(f"/contacts/{cid}", headers=api_headers)
    assert resp.status_code == 204

    # Verify record still accessible but inactive
    get_resp = client.get(f"/contacts/{cid}")
    assert get_resp.status_code == 200
    assert get_resp.json()["is_active"] is False


def test_delete_contact_not_found(client, api_headers):
    resp = client.delete(
        "/contacts/00000000-0000-0000-0000-000000000000", headers=api_headers
    )
    assert resp.status_code == 404


def test_delete_contact_requires_api_key(client):
    resp = client.delete("/contacts/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 401
