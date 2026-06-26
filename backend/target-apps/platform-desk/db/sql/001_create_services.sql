-- 001_create_services.sql
-- Create schema and services table for Platform Desk

CREATE SCHEMA IF NOT EXISTS platform_desk;
SET search_path = platform_desk, public;

CREATE TABLE IF NOT EXISTS platform_desk.services (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    owning_team TEXT NOT NULL,
    criticality_tier INT NOT NULL CHECK (criticality_tier IN (1, 2, 3)),
    active_support BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_services_name ON platform_desk.services (name);
