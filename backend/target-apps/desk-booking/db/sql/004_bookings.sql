-- Migration 004: Create bookings table with slot enum and conflict prevention
-- Desk reservations with time slot management

-- Create enum for time slots
CREATE TYPE slot_type AS ENUM ('full', 'am', 'pm');

CREATE TABLE IF NOT EXISTS bookings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    desk_id UUID NOT NULL,
    user_id UUID NOT NULL,
    booking_date DATE NOT NULL,
    slot slot_type NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_bookings_desk FOREIGN KEY (desk_id) REFERENCES desks(id) ON DELETE CASCADE,
    CONSTRAINT fk_bookings_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT unique_desk_date_slot UNIQUE (desk_id, booking_date, slot)
);

-- Index on user_id for user booking queries
CREATE INDEX IF NOT EXISTS idx_bookings_user_id ON bookings (user_id);

-- Index on booking_date for availability queries
CREATE INDEX IF NOT EXISTS idx_bookings_booking_date ON bookings (booking_date);

-- Compound index for availability queries by desk and date
CREATE INDEX IF NOT EXISTS idx_bookings_desk_date ON bookings (desk_id, booking_date);