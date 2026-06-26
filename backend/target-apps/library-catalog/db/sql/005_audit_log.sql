-- Audit log table: Track all operations for compliance and debugging
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL,
    entity_id UUID NOT NULL,
    action VARCHAR(50) NOT NULL,
    member_id UUID NULL REFERENCES members(id) ON DELETE SET NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    details JSONB NULL
);

-- Indexes for efficient audit queries and timeline analysis
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log (timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_log (entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_member ON audit_log (member_id);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log (action);

-- Comments for documentation
COMMENT ON TABLE audit_log IS 'Comprehensive audit trail for all library operations';
COMMENT ON COLUMN audit_log.entity_type IS 'Table name: books, members, loans, holds';
COMMENT ON COLUMN audit_log.entity_id IS 'Primary key of the affected entity';
COMMENT ON COLUMN audit_log.action IS 'Operation: CREATE, UPDATE, DELETE, CHECKOUT, RETURN, etc.';
COMMENT ON COLUMN audit_log.member_id IS 'Member who performed action (NULL for librarian operations)';
COMMENT ON COLUMN audit_log.details IS 'JSON payload with operation-specific metadata';