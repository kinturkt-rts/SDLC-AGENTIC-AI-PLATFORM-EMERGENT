-- Migration 005: Create blackouts table
-- Maintenance and unavailability periods for desks

CREATE TABLE IF NOT EXISTS blackouts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    desk_id UUID NOT NULL,
    starts_on DATE NOT NULL,
    ends_on DATE NOT NULL,
    reason TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_blackouts_desk FOREIGN KEY (desk_id) REFERENCES desks(id) ON DELETE CASCADE,
    CONSTRAINT blackouts_date_range_check CHECK (starts_on <= ends_on)
);

-- Index on desk_id for blackout queries
CREATE INDEX IF NOT EXISTS idx_blackouts_desk_id ON blackouts (desk_id);

-- Index on date range for availability queries
CREATE INDEX IF NOT EXISTS idx_blackouts_date_range ON blackouts (starts_on, ends_on);