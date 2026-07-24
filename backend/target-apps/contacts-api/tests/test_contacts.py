"""Contact route tests."""
import uuid


def test_list_contacts_empty(client):
    """GET /api/v1/contacts returns paginated empty list."""
    resp = client.get("/api/v1/contacts")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert "limit" in data
    assert "offset" in data


def test_create_contact_no_key(client, sample_department):
    """POST without API key returns 401."""
    resp = client.post("/api/v1/contacts", json={
        "full_name": "Test User",
        "email": "test@example.com",
        "department_id": sample_department.id,
    })
    assert resp.status_code == 401


def test_create_contact(client, api_headers, sample_department):
    """POST with API key creates contact."""
    resp = client.post(
        "/api/v1/contacts",
        json={
            "full_name": "New Person",
            "email": "new.person@example.com",
            "department_id": sample_department.id,
            "phone": "+1-555-9999",
            "title": "Manager",
        },
        headers=api_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["full_name"] == "New Person"
    assert data["email"] == "new.person@example.com"
    assert data["department_id"] == sample_department.id
    assert data["is_active"] is True


def test_create_contact_unknown_department(client, api_headers):
    """POST with non-existent department_id returns 404."""
    resp = client.post(
        "/api/v1/contacts",
        json={
            "full_name": "Orphan",
            "email": "orphan@example.com",
            "department_id": str(uuid.uuid4()),
        },
        headers=api_headers,
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Department not found"


def test_create_contact_duplicate_email(client, api_headers, sample_contact):
    """POST with duplicate email returns 409."""
    resp = client.post(
        "/api/v1/contacts",
        json={
            "full_name": "Another Alice",
            "email": sample_contact.email,
            "department_id": sample_contact.department_id,
        },
        headers=api_headers,
    )
    assert resp.status_code == 409


def test_get_contact(client, sample_contact):
    """GET /contacts/{id} returns the contact."""
    resp = client.get(f"/api/v1/contacts/{sample_contact.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == sample_contact.id
    assert data["full_name"] == sample_contact.full_name


def test_get_contact_not_found(client):
    """GET non-existent contact returns 404."""
    resp = client.get(f"/api/v1/contacts/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_patch_contact(client, api_headers, sample_contact):
    """PATCH updates contact fields and bumps updated_at."""
    original_updated = sample_contact.updated_at
    resp = client.patch(
        f"/api/v1/contacts/{sample_contact.id}",
        json={"title": "Lead Engineer"},
        headers=api_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Lead Engineer"
    # updated_at should be different from original
    assert data["updated_at"] != original_updated.isoformat()


def test_patch_contact_no_key(client, sample_contact):
    """PATCH without API key returns 401."""
    resp = client.patch(
        f"/api/v1/contacts/{sample_contact.id}",
        json={"title": "Unauthorized"},
    )
    assert resp.status_code == 401


def test_delete_contact_soft(client, api_headers, sample_contact):
    """DELETE sets is_active=False (soft-delete)."""
    resp = client.delete(
        f"/api/v1/contacts/{sample_contact.id}",
        headers=api_headers,
    )
    assert resp.status_code == 204
    # Verify soft-deleted
    get_resp = client.get(f"/api/v1/contacts/{sample_contact.id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["is_active"] is False


def test_delete_contact_no_key(client, sample_contact):
    """DELETE without API key returns 401."""
    resp = client.delete(f"/api/v1/contacts/{sample_contact.id}")
    assert resp.status_code == 401


def test_list_contacts_filter_department(client, sample_contact):
    """Filter contacts by department_id."""
    resp = client.get(f"/api/v1/contacts?department_id={sample_contact.department_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == sample_contact.id


def test_list_contacts_filter_active(client, sample_contact):
    """Filter contacts by is_active."""
    resp = client.get("/api/v1/contacts?is_active=true")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1

    resp2 = client.get("/api/v1/contacts?is_active=false")
    assert resp2.status_code == 200
    assert resp2.json()["total"] == 0


def test_list_contacts_search_q(client, sample_contact):
    """?q= searches full_name and email case-insensitively."""
    # Search by partial name
    resp = client.get("/api/v1/contacts?q=alice")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1

    # Search by partial email
    resp2 = client.get("/api/v1/contacts?q=chen@example")
    assert resp2.status_code == 200
    assert resp2.json()["total"] == 1

    # Search with no match
    resp3 = client.get("/api/v1/contacts?q=zzzzz")
    assert resp3.status_code == 200
    assert resp3.json()["total"] == 0


def test_list_contacts_pagination(client, api_headers, sample_department):
    """Pagination params work correctly."""
    # Create 3 contacts
    for i in range(3):
        client.post(
            "/api/v1/contacts",
            json={
                "full_name": f"Person {i}",
                "email": f"person{i}@example.com",
                "department_id": sample_department.id,
            },
            headers=api_headers,
        )
    # List with limit=2
    resp = client.get("/api/v1/contacts?limit=2&offset=0")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["items"]) == 2
    assert data["limit"] == 2
    assert data["offset"] == 0

    # Offset=2 gives 1 item
    resp2 = client.get("/api/v1/contacts?limit=2&offset=2")
    assert resp2.json()["total"] == 3
    assert len(resp2.json()["items"]) == 1
