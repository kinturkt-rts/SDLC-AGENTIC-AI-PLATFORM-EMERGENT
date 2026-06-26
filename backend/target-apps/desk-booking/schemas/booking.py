"""Booking Pydantic schemas."""
from __future__ import annotations

import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator


class BookingCreate(BaseModel):
    desk_id: str
    booking_date: datetime.date
    slot: Literal["full", "am", "pm"]


class BookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    desk_id: str
    user_id: str
    booking_date: datetime.date
    slot: str
    created_at: datetime.datetime

    @field_validator("id", "desk_id", "user_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v


class BookingListPage(BaseModel):
    bookings: list[BookingOut]
    total: int
    limit: int
    offset: int
