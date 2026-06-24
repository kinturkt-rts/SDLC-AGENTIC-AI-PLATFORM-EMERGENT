"""Tests for GET /audit."""


def test_list_audit_admin(client, seeded, auth_headers):
    """Admin can list global audit."""
    # First create a swap to generate audit
    headers = auth_headers("staff")
    client.post("/swaps", json={"offered_shift_id": seeded["shift1_id"]}, headers=headers)

    resp = client.get("/audit", headers=auth_headers("admin"))
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_list_audit_forbidden_staff(client, seeded, auth_headers):
    resp = client.get("/audit", headers=auth_headers("staff"))
    assert resp.status_code == 403
