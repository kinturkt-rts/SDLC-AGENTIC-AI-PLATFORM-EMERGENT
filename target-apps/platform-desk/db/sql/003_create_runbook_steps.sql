-- 003_create_runbook_steps.sql
-- Runbook steps with ordered step numbers

SET search_path = platform_desk, public;

CREATE TABLE IF NOT EXISTS platform_desk.runbook_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    runbook_id UUID NOT NULL REFERENCES platform_desk.runbooks(id),
    step_number INT NOT NULL,
    title TEXT NOT NULL,
    body_text TEXT NOT NULL,
    estimated_minutes INT,
    warning_callout TEXT
);

CREATE INDEX IF NOT EXISTS idx_steps_runbook
    ON platform_desk.runbook_steps (runbook_id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_steps_runbook_number
    ON platform_desk.runbook_steps (runbook_id, step_number);
