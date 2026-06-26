-- 001_create_users.sql
-- Idempotent: creates schema + users table for healthcare_clinic_bot

CREATE SCHEMA IF NOT EXISTS healthcare_clinic_bot;

CREATE TABLE IF NOT EXISTS healthcare_clinic_bot.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(80) NOT NULL,
    hashed_password TEXT NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'staff',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_users_username UNIQUE (username)
);

CREATE INDEX IF NOT EXISTS idx_users_username
    ON healthcare_clinic_bot.users (username);
