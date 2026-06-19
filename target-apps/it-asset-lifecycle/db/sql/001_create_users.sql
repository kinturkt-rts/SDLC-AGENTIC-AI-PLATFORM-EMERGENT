-- 001_create_users.sql
-- Creates the users table with role enum for RBAC

SET search_path TO it_asset_lifecycle, public;

CREATE SCHEMA IF NOT EXISTS it_asset_lifecycle;

DO $$ BEGIN
    CREATE TYPE it_asset_lifecycle.user_role AS ENUM ('it_admin', 'it_staff', 'finance_readonly');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS it_asset_lifecycle.users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username        VARCHAR(100) NOT NULL,
    password_hash   TEXT NOT NULL,
    role            it_asset_lifecycle.user_role NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_users_username UNIQUE (username)
);
