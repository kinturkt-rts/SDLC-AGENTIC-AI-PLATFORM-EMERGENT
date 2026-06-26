-- 005_alter_embedding_1024.sql
-- Align embedding column with amazon.titan-embed-text-v2:0 (1024 dimensions)

SET search_path TO bug_deduper, public;

DROP INDEX IF EXISTS bug_deduper.idx_bugs_embedding_hnsw;

UPDATE bug_deduper.bugs SET embedding = NULL WHERE embedding IS NOT NULL;

ALTER TABLE bug_deduper.bugs
    ALTER COLUMN embedding TYPE vector(1024);

CREATE INDEX IF NOT EXISTS idx_bugs_embedding_hnsw
    ON bug_deduper.bugs USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
