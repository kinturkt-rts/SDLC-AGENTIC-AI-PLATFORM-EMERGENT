-- Migration 001: users table
-- Schema: field_service_dispatch

CREATE SCHEMA IF NOT EXISTS field_service_dispatch;

CREATE TABLE IF NOT EXISTS field_service_dispatch.users (
    id UUID PRIMARY KEY,
    username TEXT NOT NULL,
    hashed_password TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('dispatcher', 'technician', 'owner')),
    technician_id UUID NULL,
    CONSTRAINT uq_users_username UNIQUE (username)
);

CREATE INDEX IF NOT EXISTS idx_users_username
    ON field_service_dispatch.users (username);
