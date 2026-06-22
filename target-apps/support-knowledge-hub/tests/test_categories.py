"""Tests for categories endpoints."""


def test_create_category(client, auth_headers, seed_users):
    """Knowledge admin can create a category."""
    headers = auth_headers("admin")
    resp = client.post("/categories", json={
        "name": "Engineering",
        "slug": "engineering",
    }, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Engineering"
    assert data["slug"] == "engineering"


def test_create_category_forbidden(client, auth_headers, seed_users):
    """Contributor cannot create categories."""
    headers = auth_headers("contributor")
    resp = client.post("/categories", json={
        "name": "No",
        "slug": "no",
    }, headers=headers)
    assert resp.status_code == 403


def test_delete_category_no_articles(client, auth_headers, seed_category):
    """Admin can delete category with no published articles."""
    # Create a new category to delete
    headers = auth_headers("admin")
    resp = client.post("/categories", json={
        "name": "Temp",
        "slug": "temp",
    }, headers=headers)
    cat_id = resp.json()["id"]
    resp = client.delete(f"/categories/{cat_id}", headers=headers)
    assert resp.status_code == 204


def test_delete_category_with_published_articles(client, auth_headers, seed_article):
    """Cannot delete category with published articles (409)."""
    headers = auth_headers("admin")
    resp = client.delete("/categories/b2000000-0000-0000-0000-000000000001", headers=headers)
    assert resp.status_code == 409
