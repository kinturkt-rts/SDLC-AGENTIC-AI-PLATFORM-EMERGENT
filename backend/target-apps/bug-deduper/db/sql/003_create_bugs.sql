-- 003_create_bugs.sql
-- Create bugs table with pgvector embedding column and HNSW index

SET search_path TO bug_deduper, public;

CREATE TABLE IF NOT EXISTS bug_deduper.bugs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    embedding VECTOR(1536),
    status bug_deduper.bug_status NOT NULL DEFAULT 'open',
    duplicate_of UUID REFERENCES bug_deduper.bugs(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- HNSW index for cosine similarity search on embeddings
CREATE INDEX IF NOT EXISTS idx_bugs_embedding_hnsw
    ON bug_deduper.bugs USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Index on status for filtering open bugs in dedup queries
CREATE INDEX IF NOT EXISTS idx_bugs_status
    ON bug_deduper.bugs (status);
