-- 003_findings.sql: Core findings table with workflow state management
-- Supports optimistic locking and role-based access

DO $$ BEGIN
    CREATE TYPE finding_severity AS ENUM ('low', 'medium', 'high', 'critical');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE finding_status AS ENUM ('draft', 'assigned', 'in_progress', 'pending_verification', 'verified', 'closed');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

CREATE TABLE IF NOT EXISTS findings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    audit_id UUID NOT NULL REFERENCES audits(id),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    severity finding_severity NOT NULL,
    status finding_status NOT NULL DEFAULT 'draft',
    assigned_to UUID REFERENCES users(id),
    due_date DATE,
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    version INTEGER NOT NULL DEFAULT 1
);

-- Composite index for efficient filtering by status, severity, and due date
CREATE INDEX IF NOT EXISTS idx_findings_status_severity_due ON findings(status, severity, due_date);
CREATE INDEX IF NOT EXISTS idx_findings_assigned_to ON findings(assigned_to);
CREATE INDEX IF NOT EXISTS idx_findings_audit_id ON findings(audit_id);
CREATE INDEX IF NOT EXISTS idx_findings_created_by ON findings(created_by);