-- 005_create_change_requests.sql
SET search_path TO change_request_hub;

CREATE TABLE IF NOT EXISTS change_requests (
    id UUID PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    service_id UUID NOT NULL REFERENCES services(id),
    target_environment_id UUID NOT NULL REFERENCES environments(id),
    change_type TEXT NOT NULL CHECK (change_type IN ('standard', 'normal', 'emergency')),
    risk TEXT NOT NULL CHECK (risk IN ('low', 'medium', 'high', 'critical')),
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft', 'submitted', 'approved', 'rejected',
        'scheduled', 'implementing', 'completed', 'closed'
    )),
    requester_id UUID NOT NULL REFERENCES users(id),
    implementer_id UUID REFERENCES users(id),
    planned_start TIMESTAMPTZ NOT NULL,
    planned_end TIMESTAMPTZ NOT NULL,
    rollback_plan TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    submitted_at TIMESTAMPTZ,
    approved_at TIMESTAMPTZ,
    scheduled_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_change_requests_status ON change_requests (status);
CREATE INDEX IF NOT EXISTS idx_change_requests_requester ON change_requests (requester_id);
CREATE INDEX IF NOT EXISTS idx_change_requests_implementer ON change_requests (implementer_id);
CREATE INDEX IF NOT EXISTS idx_change_requests_planned_end ON change_requests (planned_end);
CREATE INDEX IF NOT EXISTS idx_change_requests_created_at ON change_requests (created_at);
CREATE INDEX IF NOT EXISTS idx_change_requests_service ON change_requests (service_id);
CREATE INDEX IF NOT EXISTS idx_change_requests_env ON change_requests (target_environment_id);
