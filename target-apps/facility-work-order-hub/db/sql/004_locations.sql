-- 004_locations.sql
-- Locations table

SET search_path TO facility_work_order_hub;

CREATE TABLE IF NOT EXISTS locations (
    id UUID PRIMARY KEY,
    site_id UUID NOT NULL REFERENCES sites(id),
    floor TEXT NOT NULL,
    area_label TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_locations_site_id ON locations (site_id);
