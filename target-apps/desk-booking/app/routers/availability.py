"""Availability router — public read."""
from __future__ import annotations

import datetime
from typing import Optional

from fastapi import APIRouter, Query
from sqlalchemy.orm import joinedload

from app.dependencies import DbSession
from app.models.blackout import Blackout
from app.models.booking import Booking
from app.models.desk import Desk
from app.models.zone import Zone
from schemas.desk import DeskAvailability

router = APIRouter()


@router.get("/", response_model=list[DeskAvailability])
def get_availability(
    db: DbSession,
    date: datetime.date = Query(..., description="Date to check availability (YYYY-MM-DD)"),
    zone_id: Optional[str] = Query(default=None, description="Filter by zone ID"),
):
    """Get per-desk availability for a specific date."""
    query = db.query(Desk).filter(Desk.is_active.is_(True)).options(joinedload(Desk.zone))

    if zone_id:
        query = query.filter(Desk.zone_id == zone_id)

    desks = query.all()
    result: list[DeskAvailability] = []

    for desk in desks:
        # Check blackout
        blackout = (
            db.query(Blackout)
            .filter(
                Blackout.desk_id == desk.id,
                Blackout.starts_on <= date,
                Blackout.ends_on >= date,
            )
            .first()
        )
        if blackout:
            result.append(
                DeskAvailability(
                    desk_id=desk.id,
                    label=desk.label,
                    zone_name=desk.zone.name if desk.zone else "",
                    available_slots=[],
                )
            )
            continue

        # Get existing bookings for this desk on this date
        bookings = (
            db.query(Booking)
            .filter(Booking.desk_id == desk.id, Booking.booking_date == date)
            .all()
        )
        booked_slots = [b.slot for b in bookings]

        available_slots: list[str] = []
        if "full" not in booked_slots and "am" not in booked_slots and "pm" not in booked_slots:
            available_slots.append("full")
        if "full" not in booked_slots and "am" not in booked_slots:
            available_slots.append("am")
        if "full" not in booked_slots and "pm" not in booked_slots:
            available_slots.append("pm")

        result.append(
            DeskAvailability(
                desk_id=desk.id,
                label=desk.label,
                zone_name=desk.zone.name if desk.zone else "",
                available_slots=available_slots,
            )
        )

    return result
