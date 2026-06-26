"""Dashboard tests."""


def test_dashboard_manager_access(client, manager_headers):
    resp = client.get("/api/v1/dashboard/summary", headers=manager_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "counts_by_status" in data
    assert "overdue_scheduled_count" in data


def test_dashboard_leadership_access(client, leadership_headers):
    resp = client.get("/api/v1/dashboard/summary", headers=leadership_headers)
    assert resp.status_code == 200


def test_dashboard_requester_forbidden(client, requester_headers):
    resp = client.get("/api/v1/dashboard/summary", headers=requester_headers)
    assert resp.status_code == 403
