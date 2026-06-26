"""Tests for technicians endpoint."""


def test_list_technicians(client, seed_users):
    resp = client.get(
        "/technicians",
        headers=seed_users["dispatcher_headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    # Only active techs by default
    assert all(t["is_active"] for t in data)
    assert len(data) >= 1


def test_list_technicians_include_inactive(client, seed_users):
    resp = client.get(
        "/technicians?active_only=false",
        headers=seed_users["dispatcher_headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 2  # includes inactive
    inactive = [t for t in data if not t["is_active"]]
    assert len(inactive) >= 1


def test_list_technicians_unauthenticated(client):
    resp = client.get("/technicians")
    assert resp.status_code == 401
