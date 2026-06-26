"""Bookings router — employee CRUD with conflict detection."""
from __future__ import annotations

import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import func, or_, select

from app.config import get_settings
from app.dependencies import DbSession, get_current_user, require_admin_key
from app.models.blackout import Blackout
from app.models.booking import Booking
from app.models.desk import Desk
from app.models.user import User
from schemas.booking import BookingCreate, BookingListPage, BookingOut

router = APIRouter()


@router.post("/", response_model=BookingOut, status_code=201)
def create_booking(
    body: BookingCreate,
    db: DbSession,
    current_user: User = Depends(get_current_user),
):
    """Create a desk booking with full conflict detection."""
    today = datetime.date.today()
    min_date = today
    max_date = today + datetime.timedelta(days=30)

    if body.booking_date < min_date or body.booking_date > max_date:
        raise HTTPException(
            status_code=422,
            detail=f"Booking date must be between {min_date} and {max_date}",
        )

    # One booking per user per date
    existing_user_booking = (
        db.query(Booking)
        .filter(Booking.user_id == current_user.id, Booking.booking_date == body.booking_date)
        .first()
    )
    if existing_user_booking:
        raise HTTPException(status_code=409, detail="User already has a booking on this date")

    # Check desk exists and active
    desk = db.query(Desk).filter(Desk.id == body.desk_id, Desk.is_active.is_(True)).first()
    if not desk:
        raise HTTPException(status_code=404, detail="Desk not found or not active")

    # Check blackout periods
    blackout = (
        db.query(Blackout)
        .filter(
            Blackout.desk_id == body.desk_id,
            Blackout.starts_on <= body.booking_date,
            Blackout.ends_on >= body.booking_date,
        )
        .first()
    )
    if blackout:
        raise HTTPException(
            status_code=409,
            detail=f"Desk is blocked during blackout period: {blackout.reason}",
        )

    # Check slot conflicts
    if body.slot == "full":
        conflict_filter = or_(
            Booking.slot == "full", Booking.slot == "am", Booking.slot == "pm"
        )
    else:
        conflict_filter = or_(Booking.slot == "full", Booking.slot == body.slot)

    existing_booking = (
        db.query(Booking)
        .filter(
            Booking.desk_id == body.desk_id,
            Booking.booking_date == body.booking_date,
            conflict_filter,
        )
        .first()
    )
    if existing_booking:
        raise HTTPException(
            status_code=409,
            detail=f"Booking conflict with existing booking {existing_booking.id}",
        )

    booking = Booking(
        desk_id=body.desk_id,
        user_id=current_user.id,
        booking_date=body.booking_date,
        slot=body.slot,
    )

    try:
        db.add(booking)
        db.commit()
        db.refresh(booking)
        return booking
    except Exception as e:
        db.rollback()
        if "unique_desk_date_slot" in str(e).lower():
            raise HTTPException(status_code=409, detail="Booking conflict detected")
        raise HTTPException(status_code=500, detail="Failed to create booking")


@router.get("/mine", response_model=BookingListPage)
def list_my_bookings(
    db: DbSession,
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """List current user's bookings with pagination."""
    total = (
        db.scalar(select(func.count(Booking.id)).where(Booking.user_id == current_user.id))
        or 0
    )
    bookings = (
        db.scalars(
            select(Booking)
            .where(Booking.user_id == current_user.id)
            .order_by(Booking.booking_date.desc(), Booking.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        .all()
    )
    return BookingListPage(bookings=list(bookings), total=total, limit=limit, offset=offset)


@router.delete("/{booking_id}", status_code=204, response_model=None)
def cancel_booking(
    booking_id: str,
    db: DbSession,
    current_user: User = Depends(get_current_user),
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
):
    """Cancel a booking. Owner or admin (with X-Admin-Key) can delete."""
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    # Check admin
    is_admin = False
    settings = get_settings()
    if x_admin_key and x_admin_key == settings.admin_key:
        is_admin = True

    if booking.user_id != current_user.id and not is_admin:
        raise HTTPException(status_code=403, detail="Can only cancel your own bookings")

    db.delete(booking)
    db.commit()
    return None
