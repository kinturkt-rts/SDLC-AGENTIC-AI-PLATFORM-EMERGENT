"""Category route tests (FR-4)."""

from __future__ import annotations


def test_admin_create_category_auto_slug(client, auth_headers):
    r = client.post(
        "/categories",
        headers=auth_headers("admin"),
        json={"name": "Office Supplies"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Office Supplies"
    assert body["slug"] == "office-supplies"
    assert "id" in body and "created_at" in body


def test_create_category_duplicate_slug_409(client, auth_headers):
    headers = auth_headers("admin")
    client.post("/categories", headers=headers, json={"name": "Hardware"})
    r = client.post("/categories", headers=headers, json={"name": "Hardware"})
    assert r.status_code == 409


def test_staff_cannot_create_category_403(client, auth_headers):
    """Role-boundary: staff POST -> 403 (FR-3, FR-4)."""
    r = client.post(
        "/categories",
        headers=auth_headers("staff"),
        json={"name": "Books"},
    )
    assert r.status_code == 403


def test_staff_can_list_categories(client, auth_headers):
    """Staff has read access — list returns paginated envelope (FR-4/6)."""
    r = client.get("/categories", headers=auth_headers("staff"))
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) >= {"items", "total", "limit", "offset"}
    assert isinstance(body["items"], list)
    assert body["total"] >= 1  # seed creates "Electronics"


def test_get_category_includes_product_count(client, auth_headers, seeded):
    r = client.get(f"/categories/{seeded['category_id']}", headers=auth_headers("admin"))
    assert r.status_code == 200
    body = r.json()
    assert body["product_count"] == 1  # seed product belongs to this category


def test_get_unknown_category_404(client, auth_headers):
    r = client.get(
        "/categories/00000000-0000-0000-0000-000000000000",
        headers=auth_headers("admin"),
    )
    assert r.status_code == 404


def test_patch_category_admin_only(client, auth_headers, seeded):
    """Staff cannot PATCH a category (403); admin succeeds."""
    cat_id = seeded["category_id"]
    r_staff = client.patch(
        f"/categories/{cat_id}",
        headers=auth_headers("staff"),
        json={"name": "Renamed"},
    )
    assert r_staff.status_code == 403

    r_admin = client.patch(
        f"/categories/{cat_id}",
        headers=auth_headers("admin"),
        json={"name": "Consumer Electronics"},
    )
    assert r_admin.status_code == 200
    assert r_admin.json()["name"] == "Consumer Electronics"
