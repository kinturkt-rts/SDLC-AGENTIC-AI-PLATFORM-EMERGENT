-- 001_create_users.sql
-- Create users table for inventory-app (FR-1, FR-2, FR-9)

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE t.typname = 'user_role' AND n.nspname = current_schema()
    ) THEN
        CREATE TYPE user_role AS ENUM ('manager', 'staff');
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username        TEXT NOT NULL UNIQUE,
    hashed_password TEXT NOT NULL,
    role            user_role NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users (username);
