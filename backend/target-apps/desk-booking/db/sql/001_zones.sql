-- Migration 001: Create zones table
-- Hot desk booking zones (north, south, lab)

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS zones (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT zones_name_check CHECK (name IN ('north', 'south', 'lab'))
);

-- Index on name for zone lookups
CREATE INDEX IF NOT EXISTS idx_zones_name ON zones (name);