-- 006_create_api_keys.sql
-- API key store for authentication and RBAC

SET search_path = platform_desk, public;

CREATE TABLE IF NOT EXISTS platform_desk.api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key_hash TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL CHECK (role IN ('viewer', 'editor', 'admin')),
    label TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_apikeys_hash
    ON platform_desk.api_keys (key_hash);
