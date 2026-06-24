-- 002_users.sql
SET search_path = shift_swap_board;

CREATE TABLE IF NOT EXISTS users (
    id uuid PRIMARY KEY,
    username varchar(64) NOT NULL UNIQUE,
    password_hash text NOT NULL,
    role shift_swap_board.user_role NOT NULL,
    display_name varchar(128) NOT NULL,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users (username);
