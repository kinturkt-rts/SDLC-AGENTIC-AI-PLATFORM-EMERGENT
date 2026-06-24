"""Tests for swap lifecycle."""
import uuid


def test_create_swap(client, seeded, auth_headers):
    resp = client.post(
        "/swaps",
        json={"offered_shift_id": seeded["shift1_id"]},
        headers=auth_headers("staff"),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "open"
    assert data["offered_by_user_id"] == seeded["staff1_id"]


def test_create_swap_not_owner(client, seeded, auth_headers):
    """staff_02 cannot offer staff_01's shift."""
    resp = client.post(
        "/swaps",
        json={"offered_shift_id": seeded["shift1_id"]},
        headers={"Authorization": f"Bearer {seeded['staff2_token']}"},
    )
    assert resp.status_code == 403


def test_create_swap_duplicate(client, seeded, auth_headers):
    """Second offer on same shift returns 409."""
    headers = auth_headers("staff")
    client.post("/swaps", json={"offered_shift_id": seeded["shift1_id"]}, headers=headers)
    resp = client.post("/swaps", json={"offered_shift_id": seeded["shift1_id"]}, headers=headers)
    assert resp.status_code == 409


def test_claim_swap(client, seeded, auth_headers):
    """staff_02 claims staff_01's open swap."""
    headers1 = auth_headers("staff")
    resp = client.post("/swaps", json={"offered_shift_id": seeded["shift2_id"]}, headers=headers1)
    swap_id = resp.json()["id"]

    headers2 = {"Authorization": f"Bearer {seeded['staff2_token']}"}
    resp = client.post(f"/swaps/{swap_id}/claim", headers=headers2)
    assert resp.status_code == 200
    assert resp.json()["status"] == "claimed"
    assert resp.json()["claimed_by_user_id"] == seeded["staff2_id"]


def test_claim_own_swap_forbidden(client, seeded, auth_headers):
    headers = auth_headers("staff")
    resp = client.post("/swaps", json={"offered_shift_id": seeded["shift1_id"]}, headers=headers)
    swap_id = resp.json()["id"]
    resp = client.post(f"/swaps/{swap_id}/claim", headers=headers)
    assert resp.status_code == 403


def test_approve_swap(client, seeded, auth_headers):
    """Floor lead approves a claimed swap."""
    # Create swap
    headers1 = auth_headers("staff")
    resp = client.post("/swaps", json={"offered_shift_id": seeded["shift2_id"]}, headers=headers1)
    swap_id = resp.json()["id"]

    # Claim
    headers2 = {"Authorization": f"Bearer {seeded['staff2_token']}"}
    client.post(f"/swaps/{swap_id}/claim", headers=headers2)

    # Approve
    lead_headers = auth_headers("floor_lead")
    resp = client.post(f"/swaps/{swap_id}/approve", json={}, headers=lead_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"


def test_deny_swap(client, seeded, auth_headers):
    """Floor lead denies a claimed swap."""
    headers1 = auth_headers("staff")
    resp = client.post("/swaps", json={"offered_shift_id": seeded["shift1_id"]}, headers=headers1)
    swap_id = resp.json()["id"]

    headers2 = {"Authorization": f"Bearer {seeded['staff2_token']}"}
    client.post(f"/swaps/{swap_id}/claim", headers=headers2)

    lead_headers = auth_headers("floor_lead")
    resp = client.post(f"/swaps/{swap_id}/deny", json={"decision_note": "Not needed"}, headers=lead_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "denied"


def test_cancel_swap(client, seeded, auth_headers):
    headers = auth_headers("staff")
    resp = client.post("/swaps", json={"offered_shift_id": seeded["shift1_id"]}, headers=headers)
    swap_id = resp.json()["id"]
    resp = client.post(f"/swaps/{swap_id}/cancel", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


def test_cancel_not_offerer(client, seeded, auth_headers):
    headers1 = auth_headers("staff")
    resp = client.post("/swaps", json={"offered_shift_id": seeded["shift1_id"]}, headers=headers1)
    swap_id = resp.json()["id"]

    headers2 = {"Authorization": f"Bearer {seeded['staff2_token']}"}
    resp = client.post(f"/swaps/{swap_id}/cancel", headers=headers2)
    assert resp.status_code == 403


def test_list_swaps(client, seeded, auth_headers):
    headers = auth_headers("staff")
    client.post("/swaps", json={"offered_shift_id": seeded["shift1_id"]}, headers=headers)
    resp = client.get("/swaps", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_swap_audit(client, seeded, auth_headers):
    """Audit log populated on create."""
    headers = auth_headers("staff")
    resp = client.post("/swaps", json={"offered_shift_id": seeded["shift1_id"]}, headers=headers)
    swap_id = resp.json()["id"]

    lead_headers = auth_headers("floor_lead")
    resp = client.get(f"/swaps/{swap_id}/audit", headers=lead_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["action"] == "created"


def test_swap_audit_forbidden_staff(client, seeded, auth_headers):
    headers = auth_headers("staff")
    resp = client.post("/swaps", json={"offered_shift_id": seeded["shift1_id"]}, headers=headers)
    swap_id = resp.json()["id"]
    resp = client.get(f"/swaps/{swap_id}/audit", headers=headers)
    assert resp.status_code == 403
