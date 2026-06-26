-- Migration 007: Create audit_log table
-- Schema: training_compliance

CREATE TABLE IF NOT EXISTS training_compliance.audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    action TEXT NOT NULL,
    entity TEXT,
    entity_id UUID NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
    detail JSONB NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_log_user_id
    ON training_compliance.audit_log (user_id);

CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp
    ON training_compliance.audit_log (timestamp);
