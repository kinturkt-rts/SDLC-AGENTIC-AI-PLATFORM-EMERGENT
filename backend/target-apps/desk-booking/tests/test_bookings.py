"""Booking endpoint tests."""
import datetime

from app.models.blackout import Blackout
from app.models.booking import Booking


def test_create_booking_success(client, sample_desk, auth_headers):
    """POST /bookings with valid data returns 201."""
    tomorrow = datetime.date.today() + datetime.timedelta(days=1)
    response = client.post(
        "/bookings/",
        json={
            "desk_id": sample_desk.id,
            "booking_date": tomorrow.isoformat(),
            "slot": "full",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["desk_id"] == sample_desk.id
    assert data["slot"] == "full"
    assert data["booking_date"] == tomorrow.isoformat()


def test_create_booking_slot_conflict_full_vs_am(client, sample_desk, sample_user, second_user, auth_headers, db_session):
    """Full-day booking conflicts with existing AM booking."""
    tomorrow = datetime.date.today() + datetime.timedelta(days=1)
    # Create AM booking for second user
    existing = Booking(
        desk_id=sample_desk.id,
        user_id=second_user.id,
        booking_date=tomorrow,
        slot="am",
    )
    db_session.add(existing)
    db_session.commit()

    response = client.post(
        "/bookings/",
        json={
            "desk_id": sample_desk.id,
            "booking_date": tomorrow.isoformat(),
            "slot": "full",
        },
        headers=auth_headers,
    )
    assert response.status_code == 409
    assert "conflict" in response.json()["detail"].lower()


def test_am_pm_same_desk_ok(client, sample_desk, sample_user, second_user, db_session):
    """AM + PM on same desk/date is allowed (different users, different dates for per-user rule)."""
    day1 = datetime.date.today() + datetime.timedelta(days=1)
    day2 = datetime.date.today() + datetime.timedelta(days=2)
    # User1 books AM on day1
    existing = Booking(
        desk_id=sample_desk.id,
        user_id=second_user.id,
        booking_date=day1,
        slot="am",
    )
    db_session.add(existing)
    db_session.commit()

    # User1(alice) books PM on day1 - this should work since AM is by bob
    response = client.post(
        "/bookings/",
        json={
            "desk_id": sample_desk.id,
            "booking_date": day1.isoformat(),
            "slot": "pm",
        },
        headers={"X-User-Token": sample_user.user_token},
    )
    assert response.status_code == 201


def test_one_booking_per_user_per_date(client, sample_desk, sample_user, sample_zone, auth_headers, db_session):
    """User cannot have 2 bookings on the same date."""
    from app.models.desk import Desk
    tomorrow = datetime.date.today() + datetime.timedelta(days=1)

    # Create another desk
    desk2 = Desk(
        id="22222222-2222-2222-2222-222222222099",
        zone_id=sample_zone.id,
        label="N-99",
        is_active=True,
    )
    db_session.add(desk2)
    db_session.commit()

    # Book desk1
    response = client.post(
        "/bookings/",
        json={
            "desk_id": sample_desk.id,
            "booking_date": tomorrow.isoformat(),
            "slot": "am",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201

    # Try to book desk2 on same date
    response = client.post(
        "/bookings/",
        json={
            "desk_id": desk2.id,
            "booking_date": tomorrow.isoformat(),
            "slot": "pm",
        },
        headers=auth_headers,
    )
    assert response.status_code == 409
    assert "already has a booking" in response.json()["detail"].lower()


def test_booking_outside_window(client, sample_desk, auth_headers):
    """Booking > 30 days in future returns 422."""
    far_future = datetime.date.today() + datetime.timedelta(days=31)
    response = client.post(
        "/bookings/",
        json={
            "desk_id": sample_desk.id,
            "booking_date": far_future.isoformat(),
            "slot": "full",
        },
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert "date must be between" in response.json()["detail"].lower()


def test_booking_in_past(client, sample_desk, auth_headers):
    """Booking in the past returns 422."""
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    response = client.post(
        "/bookings/",
        json={
            "desk_id": sample_desk.id,
            "booking_date": yesterday.isoformat(),
            "slot": "full",
        },
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_booking_on_blackout(client, sample_desk, auth_headers, db_session):
    """Booking on a blacked-out date returns 409."""
    tomorrow = datetime.date.today() + datetime.timedelta(days=1)
    blackout = Blackout(
        desk_id=sample_desk.id,
        starts_on=tomorrow,
        ends_on=tomorrow,
        reason="Maintenance",
    )
    db_session.add(blackout)
    db_session.commit()

    response = client.post(
        "/bookings/",
        json={
            "desk_id": sample_desk.id,
            "booking_date": tomorrow.isoformat(),
            "slot": "full",
        },
        headers=auth_headers,
    )
    assert response.status_code == 409
    assert "blackout" in response.json()["detail"].lower()


def test_list_my_bookings(client, sample_desk, sample_user, auth_headers, db_session):
    """GET /bookings/mine returns user's bookings."""
    tomorrow = datetime.date.today() + datetime.timedelta(days=1)
    booking = Booking(
        desk_id=sample_desk.id,
        user_id=sample_user.id,
        booking_date=tomorrow,
        slot="am",
    )
    db_session.add(booking)
    db_session.commit()

    response = client.get("/bookings/mine", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["bookings"]) == 1
    assert data["bookings"][0]["user_id"] == sample_user.id


def test_cancel_booking_owner(client, sample_desk, sample_user, auth_headers, db_session):
    """DELETE /bookings/{id} by owner returns 204."""
    tomorrow = datetime.date.today() + datetime.timedelta(days=1)
    booking = Booking(
        id="44444444-4444-4444-4444-444444444001",
        desk_id=sample_desk.id,
        user_id=sample_user.id,
        booking_date=tomorrow,
        slot="am",
    )
    db_session.add(booking)
    db_session.commit()

    response = client.delete(f"/bookings/{booking.id}", headers=auth_headers)
    assert response.status_code == 204


def test_cancel_booking_not_owner(client, sample_desk, sample_user, second_user, auth_headers, db_session):
    """DELETE /bookings/{id} by non-owner returns 403."""
    tomorrow = datetime.date.today() + datetime.timedelta(days=1)
    booking = Booking(
        id="44444444-4444-4444-4444-444444444002",
        desk_id=sample_desk.id,
        user_id=second_user.id,
        booking_date=tomorrow,
        slot="am",
    )
    db_session.add(booking)
    db_session.commit()

    response = client.delete(f"/bookings/{booking.id}", headers=auth_headers)
    assert response.status_code == 403
    assert "only cancel your own" in response.json()["detail"].lower()


def test_cancel_booking_admin(client, sample_desk, sample_user, second_user, db_session):
    """DELETE /bookings/{id} by admin succeeds even if not owner."""
    tomorrow = datetime.date.today() + datetime.timedelta(days=1)
    booking = Booking(
        id="44444444-4444-4444-4444-444444444003",
        desk_id=sample_desk.id,
        user_id=second_user.id,
        booking_date=tomorrow,
        slot="am",
    )
    db_session.add(booking)
    db_session.commit()

    # Alice with admin key can delete Bob's booking
    headers = {"X-User-Token": sample_user.user_token, "X-Admin-Key": "test-admin-key-123"}
    response = client.delete(f"/bookings/{booking.id}", headers=headers)
    assert response.status_code == 204


def test_create_booking_unauthorized(client, sample_desk):
    """POST /bookings without token returns 401."""
    tomorrow = datetime.date.today() + datetime.timedelta(days=1)
    response = client.post(
        "/bookings/",
        json={
            "desk_id": sample_desk.id,
            "booking_date": tomorrow.isoformat(),
            "slot": "full",
        },
    )
    assert response.status_code == 401
    assert "Missing X-User-Token header" in response.json()["detail"]
