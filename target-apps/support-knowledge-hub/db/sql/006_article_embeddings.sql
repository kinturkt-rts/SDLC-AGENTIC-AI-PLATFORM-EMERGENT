-- 006_article_embeddings.sql
SET search_path TO support_knowledge_hub, public;

CREATE TABLE IF NOT EXISTS article_embeddings (
    id            UUID PRIMARY KEY,
    article_id    UUID NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    chunk_index   INT NOT NULL,
    chunk_text    TEXT NOT NULL,
    embedding     vector(384) NOT NULL,
    model_version TEXT NOT NULL,
    embedded_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (article_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_article_embeddings_hnsw
    ON article_embeddings
    USING hnsw (embedding vector_cosine_ops);
