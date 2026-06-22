-- 004_create_api_keys.sql
-- Create api_keys table for storing hashed API keys with tier information

SET search_path TO bug_deduper, public;

CREATE TABLE IF NOT EXISTS bug_deduper.api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key_hash TEXT NOT NULL UNIQUE,
    tier bug_deduper.key_tier NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
