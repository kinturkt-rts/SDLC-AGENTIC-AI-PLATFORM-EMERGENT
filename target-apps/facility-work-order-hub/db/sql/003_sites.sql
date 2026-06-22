-- 003_sites.sql
-- Sites table

SET search_path TO facility_work_order_hub;

CREATE TABLE IF NOT EXISTS sites (
    id UUID PRIMARY KEY,
    site_code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    address_line TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_sites_active ON sites (active);
