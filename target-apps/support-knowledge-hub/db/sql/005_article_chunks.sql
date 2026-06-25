-- 005_article_chunks.sql
SET search_path TO support_knowledge_hub, public;

CREATE TABLE IF NOT EXISTS article_chunks (
    id              uuid PRIMARY KEY,
    article_id      uuid NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    chunk_index     int NOT NULL,
    chunk_text      text NOT NULL,
    embedding       vector(1024) NOT NULL,
    UNIQUE (article_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_article_chunks_embedding
    ON article_chunks
    USING hnsw (embedding vector_cosine_ops);
