-- 008_create_status_history.sql
SET search_path TO change_request_hub;

CREATE TABLE IF NOT EXISTS status_history (
    id UUID PRIMARY KEY,
    change_id UUID NOT NULL REFERENCES change_requests(id),
    from_status TEXT,
    to_status TEXT NOT NULL,
    actor_id UUID NOT NULL REFERENCES users(id),
    changed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_status_history_change_time ON status_history (change_id, changed_at);
