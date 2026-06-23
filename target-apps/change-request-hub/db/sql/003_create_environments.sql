-- 003_create_environments.sql
SET search_path TO change_request_hub;

CREATE TABLE IF NOT EXISTS environments (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    sort_order INT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
