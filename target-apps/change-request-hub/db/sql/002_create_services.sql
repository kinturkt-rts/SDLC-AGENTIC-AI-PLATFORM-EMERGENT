-- 002_create_services.sql
SET search_path TO change_request_hub;

CREATE TABLE IF NOT EXISTS services (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    owner_team TEXT NOT NULL,
    tier TEXT NOT NULL CHECK (tier IN ('tier1', 'tier2', 'tier3')),
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_services_active ON services (active);
