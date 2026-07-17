-- 003_create_api_keys.sql
-- API keys for manager/admin auth (NFR-3)

CREATE TABLE IF NOT EXISTS api_keys (
    id SERIAL PRIMARY KEY,
    key_hash VARCHAR(256) UNIQUE NOT NULL,
    role VARCHAR(20) NOT NULL,
    owner_label VARCHAR(200),
    team_ids INT[],
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash ON api_keys (key_hash);
