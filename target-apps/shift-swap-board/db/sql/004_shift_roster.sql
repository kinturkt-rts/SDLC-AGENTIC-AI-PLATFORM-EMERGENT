-- 004_shift_roster.sql
SET search_path = shift_swap_board;

CREATE TABLE IF NOT EXISTS shift_roster (
    id uuid PRIMARY KEY,
    staff_id uuid NOT NULL REFERENCES staff_profiles(id),
    shift_date date NOT NULL,
    shift_window shift_swap_board.shift_window NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (staff_id, shift_date, shift_window)
);

CREATE INDEX IF NOT EXISTS idx_shift_roster_shift_date ON shift_roster (shift_date);
