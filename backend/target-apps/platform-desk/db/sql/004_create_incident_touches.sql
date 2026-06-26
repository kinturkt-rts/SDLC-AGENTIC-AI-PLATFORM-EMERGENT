-- 004_create_incident_touches.sql
-- Incident touch log (no PII stored; role only)

SET search_path = platform_desk, public;

CREATE TABLE IF NOT EXISTS platform_desk.incident_touches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    runbook_id UUID NOT NULL REFERENCES platform_desk.runbooks(id),
    step_number INT,
    ticket_reference TEXT NOT NULL,
    notes TEXT,
    role TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_touches_runbook_created
    ON platform_desk.incident_touches (runbook_id, created_at);
