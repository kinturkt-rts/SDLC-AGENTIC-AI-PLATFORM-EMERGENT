-- 003_staff_profiles.sql
SET search_path = shift_swap_board;

CREATE TABLE IF NOT EXISTS staff_profiles (
    id uuid PRIMARY KEY,
    user_id uuid NOT NULL UNIQUE REFERENCES users(id),
    employee_code varchar(32) UNIQUE
);
