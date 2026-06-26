"""Article endpoint tests."""


def test_create_article_as_contributor(client, seed_users, seed_category):
    headers = {"Authorization": f"Bearer {seed_users['contributor_token']}"}
    resp = client.post(
        "/api/v1/articles",
        json={"title": "Test Article", "body": "Body text", "category_id": seed_category, "tags": ["test"]},
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Test Article"
    assert data["state"] == "draft"
    assert data["author_id"] == seed_users["contributor_id"]


def test_create_article_forbidden_for_employee(client, seed_users, seed_category):
    headers = {"Authorization": f"Bearer {seed_users['employee_token']}"}
    resp = client.post(
        "/api/v1/articles",
        json={"title": "X", "body": "Y", "category_id": seed_category},
        headers=headers,
    )
    assert resp.status_code == 403


def test_list_articles_employee_sees_published(client, seed_users, seed_article):
    headers = {"Authorization": f"Bearer {seed_users['employee_token']}"}
    resp = client.get("/api/v1/articles", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    for art in data:
        assert art["state"] == "published"


def test_get_article_published(client, seed_users, seed_article):
    headers = {"Authorization": f"Bearer {seed_users['employee_token']}"}
    resp = client.get(f"/api/v1/articles/{seed_article}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == seed_article


def test_patch_article_publish(client, seed_users, seed_category, db_session):
    """Contributor publishes own draft."""
    from app.models.article import Article

    art = Article(
        id="c3000000-0000-0000-0000-000000000099",
        title="Draft Article",
        body="Some body",
        category_id=seed_category,
        tags=[],
        author_id=seed_users["contributor_id"],
        state="draft",
    )
    db_session.add(art)
    db_session.commit()

    headers = {"Authorization": f"Bearer {seed_users['contributor_token']}"}
    resp = client.patch(
        f"/api/v1/articles/{art.id}",
        json={"state": "published"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["state"] == "published"


def test_patch_article_forbidden_other_contributor(client, seed_users, seed_article):
    """Contributor 2 cannot modify contributor 1's article."""
    headers = {"Authorization": f"Bearer {seed_users['contributor2_token']}"}
    resp = client.patch(
        f"/api/v1/articles/{seed_article}",
        json={"title": "Hijacked"},
        headers=headers,
    )
    assert resp.status_code == 403


def test_unauthenticated_request_401(client):
    resp = client.get("/api/v1/articles")
    assert resp.status_code in (401, 403)
