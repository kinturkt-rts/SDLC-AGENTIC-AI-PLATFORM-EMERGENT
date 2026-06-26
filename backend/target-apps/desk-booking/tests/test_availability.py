"""Availability endpoint tests."""
import datetime

from app.models.blackout import Blackout
from app.models.booking import Booking


def test_availability_all_free(client, sample_desk):
    """GET /availability with no bookings shows all slots available."""
    tomorrow = datetime.date.today() + datetime.timedelta(days=1)
    response = client.get(f"/availability/?date={tomorrow.isoformat()}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["desk_id"] == sample_desk.id
    assert data[0]["label"] == "N-01"
    assert data[0]["zone_name"] == "north"
    assert set(data[0]["available_slots"]) == {"full", "am", "pm"}


def test_availability_with_am_booking(client, sample_desk, sample_user, db_session):
    """AM booking removes 'full' and 'am' from available slots."""
    tomorrow = datetime.date.today() + datetime.timedelta(days=1)
    booking = Booking(
        desk_id=sample_desk.id,
        user_id=sample_user.id,
        booking_date=tomorrow,
        slot="am",
    )
    db_session.add(booking)
    db_session.commit()

    response = client.get(f"/availability/?date={tomorrow.isoformat()}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["available_slots"] == ["pm"]


def test_availability_with_full_booking(client, sample_desk, sample_user, db_session):
    """Full-day booking removes all slots."""
    tomorrow = datetime.date.today() + datetime.timedelta(days=1)
    booking = Booking(
        desk_id=sample_desk.id,
        user_id=sample_user.id,
        booking_date=tomorrow,
        slot="full",
    )
    db_session.add(booking)
    db_session.commit()

    response = client.get(f"/availability/?date={tomorrow.isoformat()}")
    assert response.status_code == 200
    data = response.json()
    assert data[0]["available_slots"] == []


def test_availability_blackout(client, sample_desk, db_session):
    """Blackout period means no slots available."""
    tomorrow = datetime.date.today() + datetime.timedelta(days=1)
    blackout = Blackout(
        desk_id=sample_desk.id,
        starts_on=tomorrow,
        ends_on=tomorrow,
        reason="Maintenance",
    )
    db_session.add(blackout)
    db_session.commit()

    response = client.get(f"/availability/?date={tomorrow.isoformat()}")
    assert response.status_code == 200
    data = response.json()
    assert data[0]["available_slots"] == []


def test_availability_by_zone(client, sample_desk, sample_zone):
    """GET /availability?zone_id=x filters by zone."""
    tomorrow = datetime.date.today() + datetime.timedelta(days=1)
    response = client.get(
        f"/availability/?date={tomorrow.isoformat()}&zone_id={sample_zone.id}"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["zone_name"] == "north"


def test_availability_no_match_zone(client, sample_desk):
    """GET /availability with non-matching zone_id returns empty."""
    tomorrow = datetime.date.today() + datetime.timedelta(days=1)
    response = client.get(
        f"/availability/?date={tomorrow.isoformat()}&zone_id=99999999-9999-9999-9999-999999999999"
    )
    assert response.status_code == 200
    assert response.json() == []
