"""Search endpoint tests."""


def test_search_returns_results(client, seed_users, seed_article):
    headers = {"Authorization": f"Bearer {seed_users['employee_token']}"}
    resp = client.post(
        "/api/v1/search",
        json={"query": "VPN"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["title"] == "How to Reset Your VPN Connection"


def test_search_no_results(client, seed_users, seed_article):
    headers = {"Authorization": f"Bearer {seed_users['employee_token']}"}
    resp = client.post(
        "/api/v1/search",
        json={"query": "nonexistent_topic_xyz"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 0


def test_search_requires_auth(client):
    resp = client.post("/api/v1/search", json={"query": "VPN"})
    assert resp.status_code in (401, 403)
