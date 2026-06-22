"""Tests for pinned articles."""

from datetime import datetime


def _ts(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


def test_pin_article(client, auth_headers, seed_article):
    """Knowledge admin can pin a published article."""
    headers = auth_headers("admin")
    resp = client.post("/categories/b2000000-0000-0000-0000-000000000001/pins", json={
        "article_id": "c3000000-0000-0000-0000-000000000001",
    }, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["article_id"] == "c3000000-0000-0000-0000-000000000001"
    assert data["category_id"] == "b2000000-0000-0000-0000-000000000001"


def test_pin_article_contributor_forbidden(client, auth_headers, seed_article):
    """Contributor cannot pin articles."""
    headers = auth_headers("contributor")
    resp = client.post("/categories/b2000000-0000-0000-0000-000000000001/pins", json={
        "article_id": "c3000000-0000-0000-0000-000000000001",
    }, headers=headers)
    assert resp.status_code == 403


def test_pin_max_5(client, auth_headers, seed_category, db_session, seed_users):
    """Cannot pin more than 5 articles per category."""
    from app.models.article import Article
    from app.models.pinned_article import PinnedArticle
    import uuid

    # Create 5 published articles and pin them
    for i in range(5):
        art_id = str(uuid.uuid4())
        art = Article(
            id=art_id,
            title=f"Article {i}",
            body=f"Body {i}",
            category_id="b2000000-0000-0000-0000-000000000001",
            tags=[],
            author_id="a1000000-0000-0000-0000-000000000002",
            status="published",
            created_at=_ts("2024-01-20T10:00:00+00:00"),
            updated_at=_ts("2024-01-20T10:00:00+00:00"),
            published_at=_ts("2024-01-20T10:00:00+00:00"),
        )
        db_session.add(art)
        db_session.flush()
        pin = PinnedArticle(
            id=str(uuid.uuid4()),
            category_id="b2000000-0000-0000-0000-000000000001",
            article_id=art_id,
            pinned_by="a1000000-0000-0000-0000-000000000001",
            pinned_at=_ts("2024-01-21T09:00:00+00:00"),
        )
        db_session.add(pin)
    db_session.commit()

    # Create 6th article
    sixth_id = str(uuid.uuid4())
    art6 = Article(
        id=sixth_id,
        title="Article 6",
        body="Body 6",
        category_id="b2000000-0000-0000-0000-000000000001",
        tags=[],
        author_id="a1000000-0000-0000-0000-000000000002",
        status="published",
        created_at=_ts("2024-01-20T10:00:00+00:00"),
        updated_at=_ts("2024-01-20T10:00:00+00:00"),
        published_at=_ts("2024-01-20T10:00:00+00:00"),
    )
    db_session.add(art6)
    db_session.commit()

    headers = auth_headers("admin")
    resp = client.post("/categories/b2000000-0000-0000-0000-000000000001/pins", json={
        "article_id": sixth_id,
    }, headers=headers)
    assert resp.status_code == 422
    assert "Maximum 5" in resp.json()["detail"]


def test_pin_non_published_422(client, auth_headers, seed_category, db_session, seed_users):
    """Cannot pin a draft article."""
    from app.models.article import Article

    art = Article(
        id="c3000000-0000-0000-0000-000000000099",
        title="Draft Article",
        body="Draft body",
        category_id="b2000000-0000-0000-0000-000000000001",
        tags=[],
        author_id="a1000000-0000-0000-0000-000000000002",
        status="draft",
        created_at=_ts("2024-02-15T16:00:00+00:00"),
        updated_at=_ts("2024-02-15T16:00:00+00:00"),
    )
    db_session.add(art)
    db_session.commit()

    headers = auth_headers("admin")
    resp = client.post("/categories/b2000000-0000-0000-0000-000000000001/pins", json={
        "article_id": "c3000000-0000-0000-0000-000000000099",
    }, headers=headers)
    assert resp.status_code == 422
    assert "published" in resp.json()["detail"]
