-- Migration 002: Create desks table
-- Physical desk inventory with zone assignments

CREATE TABLE IF NOT EXISTS desks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    zone_id UUID NOT NULL,
    label TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_desks_zone FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE
);

-- Index on zone_id for availability queries
CREATE INDEX IF NOT EXISTS idx_desks_zone_id ON desks (zone_id);

-- Index on active desks for booking availability
CREATE INDEX IF NOT EXISTS idx_desks_is_active ON desks (is_active);