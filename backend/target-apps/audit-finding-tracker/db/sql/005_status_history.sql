-- 005_status_history.sql: Immutable audit trail for finding status transitions
-- Append-only table maintaining full compliance history

CREATE TABLE IF NOT EXISTS status_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    finding_id UUID NOT NULL REFERENCES findings(id) ON DELETE CASCADE,
    from_status finding_status,
    to_status finding_status NOT NULL,
    changed_by UUID NOT NULL REFERENCES users(id),
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    comment TEXT
);

-- Indexes for efficient audit trail queries
CREATE INDEX IF NOT EXISTS idx_status_history_finding_date ON status_history(finding_id, changed_at);
CREATE INDEX IF NOT EXISTS idx_status_history_changed_by ON status_history(changed_by);
CREATE INDEX IF NOT EXISTS idx_status_history_changed_at ON status_history(changed_at);