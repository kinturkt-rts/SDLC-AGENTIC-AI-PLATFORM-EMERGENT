"""Tests for GET /roster and GET /roster/mine."""


def test_list_roster(client, seeded, auth_headers):
    resp = client.get("/roster", headers=auth_headers("admin"))
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 3  # seeded 3 shifts


def test_list_roster_date_filter(client, seeded, auth_headers):
    tomorrow = seeded["tomorrow"].isoformat()
    resp = client.get(f"/roster?from={tomorrow}&to={tomorrow}", headers=auth_headers("admin"))
    assert resp.status_code == 200
    data = resp.json()
    assert all(row["shift_date"] == tomorrow for row in data)


def test_my_roster(client, seeded, auth_headers):
    resp = client.get("/roster/mine", headers=auth_headers("staff"))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 2  # staff_01 has 2 shifts
    for row in data:
        assert row["staff_id"] == seeded["sp1_id"]
