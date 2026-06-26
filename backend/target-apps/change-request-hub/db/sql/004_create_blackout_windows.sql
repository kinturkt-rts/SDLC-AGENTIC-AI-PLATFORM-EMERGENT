-- 004_create_blackout_windows.sql
SET search_path TO change_request_hub;

CREATE TABLE IF NOT EXISTS blackout_windows (
    id UUID PRIMARY KEY,
    environment_id UUID NOT NULL REFERENCES environments(id),
    start_at TIMESTAMPTZ NOT NULL,
    end_at TIMESTAMPTZ NOT NULL,
    reason TEXT NOT NULL,
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_blackout_windows_env_time
    ON blackout_windows (environment_id, start_at, end_at);
