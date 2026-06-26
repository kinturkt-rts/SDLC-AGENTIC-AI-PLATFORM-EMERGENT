"""Pins endpoint tests."""


def test_create_pin(client, seed_users, seed_article, seed_category):
    headers = {"Authorization": f"Bearer {seed_users['admin_token']}"}
    resp = client.post(
        "/api/v1/pins",
        json={"category_id": seed_category, "article_id": seed_article, "display_order": 1},
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["article_id"] == seed_article
    assert data["display_order"] == 1


def test_list_pins(client, seed_users, seed_article, seed_category, db_session):
    from app.models.pinned_article import PinnedArticle

    pin = PinnedArticle(
        id="18000000-0000-0000-0000-000000000099",
        category_id=seed_category,
        article_id=seed_article,
        pinned_by=seed_users["admin_id"],
        display_order=1,
    )
    db_session.add(pin)
    db_session.commit()

    headers = {"Authorization": f"Bearer {seed_users['employee_token']}"}
    resp = client.get(f"/api/v1/pins/{seed_category}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


def test_delete_pin(client, seed_users, seed_article, seed_category, db_session):
    from app.models.pinned_article import PinnedArticle

    pin = PinnedArticle(
        id="18000000-0000-0000-0000-000000000098",
        category_id=seed_category,
        article_id=seed_article,
        pinned_by=seed_users["admin_id"],
        display_order=1,
    )
    db_session.add(pin)
    db_session.commit()

    headers = {"Authorization": f"Bearer {seed_users['admin_token']}"}
    resp = client.delete(f"/api/v1/pins/{pin.id}", headers=headers)
    assert resp.status_code == 204


def test_pin_limit_exceeded(client, seed_users, seed_category, db_session):
    """Cannot pin more than 5 articles in one category."""
    from app.models.article import Article
    from app.models.pinned_article import PinnedArticle

    # Create 5 published articles and pin them
    for i in range(5):
        art_id = f"c300000{i}-0000-0000-0000-000000000050"
        art = Article(
            id=art_id,
            title=f"Article {i}",
            body=f"Body {i}",
            category_id=seed_category,
            tags=[],
            author_id=seed_users["contributor_id"],
            state="published",
        )
        db_session.add(art)
        pin = PinnedArticle(
            id=f"1800000{i}-0000-0000-0000-000000000050",
            category_id=seed_category,
            article_id=art_id,
            pinned_by=seed_users["admin_id"],
            display_order=i + 1,
        )
        db_session.add(pin)
    db_session.commit()

    # Create 6th published article
    art6 = Article(
        id="c3000006-0000-0000-0000-000000000050",
        title="Article 6",
        body="Body 6",
        category_id=seed_category,
        tags=[],
        author_id=seed_users["contributor_id"],
        state="published",
    )
    db_session.add(art6)
    db_session.commit()

    headers = {"Authorization": f"Bearer {seed_users['admin_token']}"}
    resp = client.post(
        "/api/v1/pins",
        json={"category_id": seed_category, "article_id": art6.id, "display_order": 6},
        headers=headers,
    )
    assert resp.status_code == 422
