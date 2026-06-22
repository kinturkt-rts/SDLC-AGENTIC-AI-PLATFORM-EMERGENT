-- pgvector for semantic similarity search
CREATE EXTENSION IF NOT EXISTS vector;

DO $$ BEGIN
    CREATE TYPE bug_status_enum AS ENUM ('open', 'closed', 'duplicate');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS bugs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(500) NOT NULL,
    description TEXT NOT NULL,
    status bug_status_enum NOT NULL DEFAULT 'open',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE bugs ADD COLUMN IF NOT EXISTS duplicate_of_id UUID;
ALTER TABLE bugs ADD COLUMN IF NOT EXISTS description_embedding vector(1024);

DO $$ BEGIN
    ALTER TABLE bugs
        ADD CONSTRAINT bugs_duplicate_of_id_fkey
        FOREIGN KEY (duplicate_of_id) REFERENCES bugs (id);
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_bugs_status ON bugs (status);
CREATE INDEX IF NOT EXISTS idx_bugs_duplicate_of ON bugs (duplicate_of_id);
