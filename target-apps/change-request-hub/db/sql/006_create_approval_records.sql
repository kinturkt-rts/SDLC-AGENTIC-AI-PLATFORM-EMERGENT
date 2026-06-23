-- 006_create_approval_records.sql
SET search_path TO change_request_hub;

CREATE TABLE IF NOT EXISTS approval_records (
    id UUID PRIMARY KEY,
    change_id UUID NOT NULL REFERENCES change_requests(id),
    approver_id UUID NOT NULL REFERENCES users(id),
    decision TEXT NOT NULL CHECK (decision IN ('approved', 'rejected')),
    comment TEXT,
    decided_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_approval_records_change ON approval_records (change_id);
