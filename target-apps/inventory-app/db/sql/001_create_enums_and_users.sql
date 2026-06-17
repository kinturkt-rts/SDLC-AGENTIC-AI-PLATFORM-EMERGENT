-- 001_create_enums_and_users.sql
-- Inventory Desk: schema bootstrap, enum types, and users table.
-- Idempotent; safe to re-run.

CREATE SCHEMA IF NOT EXISTS inventory_app;
SET search_path TO inventory_app;

-- UUID generator: prefer pgcrypto's gen_random_uuid() (Postgres 13+).
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- user_role enum: admin | staff
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE t.typname = 'user_role' AND n.nspname = 'inventory_app'
    ) THEN
        CREATE TYPE inventory_app.user_role AS ENUM ('admin', 'staff');
    END IF;
END
$$;

-- movement_reason enum: sale | restock | adjustment (created here so later
-- migrations can reference it without ordering surprises).
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE t.typname = 'movement_reason' AND n.nspname = 'inventory_app'
    ) THEN
        CREATE TYPE inventory_app.movement_reason AS ENUM ('sale', 'restock', 'adjustment');
    END IF;
END
$$;

-- users
CREATE TABLE IF NOT EXISTS inventory_app.users (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    username        text NOT NULL,
    password_hash   text NOT NULL,
    role            inventory_app.user_role NOT NULL,
    is_active       boolean NOT NULL DEFAULT true,
    created_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT users_username_key UNIQUE (username)
);

CREATE INDEX IF NOT EXISTS ix_users_username ON inventory_app.users (username);
