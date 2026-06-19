-- Create api_keys table
CREATE TABLE IF NOT EXISTS api_keys (
    key_hash VARCHAR(255) PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN NOT NULL DEFAULT true
);

-- Add unique constraint on key_hash (redundant with PK but explicit per design)
ALTER TABLE api_keys ADD CONSTRAINT IF NOT EXISTS unique_key_hash UNIQUE (key_hash);