"""Tests for articles endpoints."""


def test_create_article(client, auth_headers, seed_category):
    """Contributor can create a draft article."""
    headers = auth_headers("contributor")
    resp = client.post("/articles", json={
        "title": "Test Article",
        "body": "Test body content",
        "category_id": "b2000000-0000-0000-0000-000000000001",
        "tags": ["test"],
    }, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Test Article"
    assert data["status"] == "draft"


def test_create_article_employee_forbidden(client, auth_headers, seed_category):
    """Employee cannot create articles."""
    headers = auth_headers("employee")
    resp = client.post("/articles", json={
        "title": "Test",
        "body": "Body",
        "category_id": "b2000000-0000-0000-0000-000000000001",
    }, headers=headers)
    assert resp.status_code == 403


def test_list_articles_employee_sees_published(client, auth_headers, seed_article):
    """Employee sees only published articles."""
    headers = auth_headers("employee")
    resp = client.get("/articles", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    for art in data:
        assert art["status"] == "published"


def test_get_article(client, auth_headers, seed_article):
    """Get single published article."""
    headers = auth_headers("employee")
    resp = client.get("/articles/c3000000-0000-0000-0000-000000000001", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "How to Connect to the Corporate VPN"


def test_get_article_not_found(client, auth_headers, seed_users):
    """Nonexistent article returns 404."""
    headers = auth_headers("employee")
    resp = client.get("/articles/00000000-0000-0000-0000-000000000000", headers=headers)
    assert resp.status_code == 404


def test_patch_article(client, auth_headers, seed_article):
    """Author can update their article."""
    headers = auth_headers("contributor")
    resp = client.patch("/articles/c3000000-0000-0000-0000-000000000001", json={
        "title": "Updated VPN Guide",
    }, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Updated VPN Guide"


def test_unauthenticated_access(client):
    """Unauthenticated requests to articles return 401."""
    resp = client.get("/articles")
    assert resp.status_code == 401
