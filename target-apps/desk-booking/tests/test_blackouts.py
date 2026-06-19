"""Blackout endpoint tests."""
import datetime


def test_create_blackout(client, sample_desk, admin_headers):
    """POST /blackouts with admin key returns 201."""
    tomorrow = datetime.date.today() + datetime.timedelta(days=1)
    day_after = tomorrow + datetime.timedelta(days=1)
    response = client.post(
        "/blackouts/",
        json={
            "desk_id": sample_desk.id,
            "starts_on": tomorrow.isoformat(),
            "ends_on": day_after.isoformat(),
            "reason": "Maintenance work",
        },
        headers=admin_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["desk_id"] == sample_desk.id
    assert data["reason"] == "Maintenance work"


def test_create_blackout_unauthorized(client, sample_desk):
    """POST /blackouts without admin key returns 401."""
    tomorrow = datetime.date.today() + datetime.timedelta(days=1)
    response = client.post(
        "/blackouts/",
        json={
            "desk_id": sample_desk.id,
            "starts_on": tomorrow.isoformat(),
            "ends_on": tomorrow.isoformat(),
            "reason": "Test",
        },
    )
    assert response.status_code == 401
    assert "Invalid or missing admin key" in response.json()["detail"]


def test_create_blackout_invalid_dates(client, sample_desk, admin_headers):
    """POST /blackouts with start > end returns 422."""
    tomorrow = datetime.date.today() + datetime.timedelta(days=2)
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    response = client.post(
        "/blackouts/",
        json={
            "desk_id": sample_desk.id,
            "starts_on": tomorrow.isoformat(),
            "ends_on": yesterday.isoformat(),
            "reason": "Invalid",
        },
        headers=admin_headers,
    )
    assert response.status_code == 422
    assert "before or equal" in response.json()["detail"]


def test_list_blackouts(client, sample_desk, admin_headers, db_session):
    """GET /blackouts returns blackouts for admin."""
    from app.models.blackout import Blackout
    tomorrow = datetime.date.today() + datetime.timedelta(days=1)
    bo = Blackout(
        id="55555555-5555-5555-5555-555555555001",
        desk_id=sample_desk.id,
        starts_on=tomorrow,
        ends_on=tomorrow,
        reason="Test",
    )
    db_session.add(bo)
    db_session.commit()

    response = client.get("/blackouts/", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "55555555-5555-5555-5555-555555555001"


def test_list_blackouts_filter_desk(client, sample_desk, admin_headers, db_session):
    """GET /blackouts?desk_id=x filters by desk."""
    from app.models.blackout import Blackout
    tomorrow = datetime.date.today() + datetime.timedelta(days=1)
    bo = Blackout(
        desk_id=sample_desk.id,
        starts_on=tomorrow,
        ends_on=tomorrow,
        reason="Test",
    )
    db_session.add(bo)
    db_session.commit()

    # Should find it
    response = client.get(
        f"/blackouts/?desk_id={sample_desk.id}", headers=admin_headers
    )
    assert response.status_code == 200
    assert len(response.json()) == 1

    # Should not find it
    response = client.get(
        "/blackouts/?desk_id=99999999-9999-9999-9999-999999999999",
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert len(response.json()) == 0


def test_delete_blackout(client, sample_desk, admin_headers, db_session):
    """DELETE /blackouts/{id} returns 204."""
    from app.models.blackout import Blackout
    tomorrow = datetime.date.today() + datetime.timedelta(days=1)
    bo = Blackout(
        id="55555555-5555-5555-5555-555555555099",
        desk_id=sample_desk.id,
        starts_on=tomorrow,
        ends_on=tomorrow,
        reason="To delete",
    )
    db_session.add(bo)
    db_session.commit()

    response = client.delete(f"/blackouts/{bo.id}", headers=admin_headers)
    assert response.status_code == 204


def test_delete_blackout_not_found(client, admin_headers):
    """DELETE /blackouts/{bad_id} returns 404."""
    response = client.delete(
        "/blackouts/99999999-9999-9999-9999-999999999999", headers=admin_headers
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_delete_blackout_unauthorized(client):
    """DELETE /blackouts/{id} without admin key returns 401."""
    response = client.delete("/blackouts/55555555-5555-5555-5555-555555555001")
    assert response.status_code == 401
    assert "Invalid or missing admin key" in response.json()["detail"]
