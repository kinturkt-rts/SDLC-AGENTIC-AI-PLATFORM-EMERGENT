-- 002_audits.sql: Audit container table
-- Each audit contains multiple findings with lifecycle management

DO $$ BEGIN
    CREATE TYPE audit_status AS ENUM ('planning', 'active', 'completed', 'archived');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

CREATE TABLE IF NOT EXISTS audits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    status audit_status NOT NULL DEFAULT 'planning',
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    version INTEGER NOT NULL DEFAULT 1
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_audits_status ON audits(status);
CREATE INDEX IF NOT EXISTS idx_audits_created_by ON audits(created_by);
CREATE INDEX IF NOT EXISTS idx_audits_created_at ON audits(created_at);