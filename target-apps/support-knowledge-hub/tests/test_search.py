"""Tests for search endpoints."""


def test_search_articles(client, auth_headers, seed_article):
    """Search returns matching published articles."""
    headers = auth_headers("employee")
    resp = client.post("/search", json={
        "query": "VPN",
    }, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert "results" in data
    assert "search_event_id" in data
    # VPN article should match
    assert len(data["results"]) >= 1
    assert data["results"][0]["article_id"] == "c3000000-0000-0000-0000-000000000001"


def test_search_no_results(client, auth_headers, seed_article):
    """Search for non-matching query returns empty."""
    headers = auth_headers("employee")
    resp = client.post("/search", json={
        "query": "xyznonexistent",
    }, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["results"] == []


def test_search_unauthenticated(client):
    """Unauthenticated search returns 401."""
    resp = client.post("/search", json={"query": "test"})
    assert resp.status_code == 401
