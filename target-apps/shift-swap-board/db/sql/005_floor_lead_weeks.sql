-- 005_floor_lead_weeks.sql
SET search_path = shift_swap_board;

CREATE TABLE IF NOT EXISTS floor_lead_weeks (
    id uuid PRIMARY KEY,
    week_start date NOT NULL UNIQUE,
    floor_lead_user_id uuid NOT NULL REFERENCES users(id)
);
