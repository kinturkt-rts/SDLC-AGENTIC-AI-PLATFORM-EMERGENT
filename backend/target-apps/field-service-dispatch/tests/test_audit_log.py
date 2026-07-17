"""Audit log endpoint tests."""


def test_audit_log_dispatcher_access(client, dispatcher_headers, seed_data):
    wo_id = seed_data["wo_in_progress_id"]
    resp = client.get(f"/api/v1/work-orders/{wo_id}/audit-log", headers=dispatcher_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 2  # new->assigned, assigned->in_progress


def test_audit_log_owner_access(client, owner_headers, seed_data):
    wo_id = seed_data["wo_assigned_id"]
    resp = client.get(f"/api/v1/work-orders/{wo_id}/audit-log", headers=owner_headers)
    assert resp.status_code == 200


def test_audit_log_technician_forbidden(client, tech_headers, seed_data):
    wo_id = seed_data["wo_assigned_id"]
    resp = client.get(f"/api/v1/work-orders/{wo_id}/audit-log", headers=tech_headers)
    assert resp.status_code == 403
