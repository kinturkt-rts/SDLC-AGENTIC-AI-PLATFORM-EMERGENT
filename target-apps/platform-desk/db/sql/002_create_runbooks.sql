-- 002_create_runbooks.sql
-- Runbooks table with lifecycle status and unique active title constraint

SET search_path = platform_desk, public;

CREATE TABLE IF NOT EXISTS platform_desk.runbooks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    service_id UUID NOT NULL REFERENCES platform_desk.services(id),
    default_severity TEXT NOT NULL,
    short_summary TEXT,
    author TEXT NOT NULL,
    lifecycle_status TEXT NOT NULL DEFAULT 'draft' CHECK (lifecycle_status IN ('draft', 'active', 'retired')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_runbooks_service_status
    ON platform_desk.runbooks (service_id, lifecycle_status);

CREATE UNIQUE INDEX IF NOT EXISTS idx_runbooks_active_title_service
    ON platform_desk.runbooks (title, service_id)
    WHERE lifecycle_status = 'active';
