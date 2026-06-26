-- 007_indexes.sql: Additional performance indexes
-- Composite indexes for complex queries and reporting

-- Executive reporting indexes
CREATE INDEX IF NOT EXISTS idx_findings_due_date_status ON findings(due_date, status) WHERE due_date IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_findings_severity_status ON findings(severity, status);

-- Performance indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_audits_status_created ON audits(status, created_at);
CREATE INDEX IF NOT EXISTS idx_findings_created_at ON findings(created_at);

-- Optimize role-based data access
CREATE INDEX IF NOT EXISTS idx_findings_assigned_status ON findings(assigned_to, status) WHERE assigned_to IS NOT NULL;