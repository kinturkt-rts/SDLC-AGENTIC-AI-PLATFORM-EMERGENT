"""Tests for admin endpoints."""


def test_admin_stats_unauthenticated(client):
    response = client.get("/admin/stats")
    assert response.status_code == 401


def test_admin_stats_staff(client, staff_headers):
    response = client.get("/admin/stats", headers=staff_headers)
    assert response.status_code == 200
    data = response.json()
    assert "total_faqs" in data
    assert "total_sessions" in data
    assert "total_messages" in data
    assert "fallback_rate" in data
    assert isinstance(data["fallback_rate"], float)
