-- Reference schema for the local pgvector RAG pattern.
-- database-agent owns the real migrations; this documents the contract that
-- app/services/pgvector_retriever.py and ingestion.py expect.
--
-- vector(1024) matches amazon.titan-embed-text-v2:0. Change the dimension if the
-- design selects a different embedding model.

CREATE EXTENSION IF NOT EXISTS vector;

-- collections and documents tables are the usual metadata tables; only the
-- chunk + embedding table is RAG-specific.

CREATE TABLE IF NOT EXISTS document_chunks (
    id          BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    doc_id      UUID        NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    page        INTEGER     NOT NULL CHECK (page >= 1),
    text        TEXT        NOT NULL,
    embedding   vector(1024) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Approximate nearest-neighbour index (cosine). Build AFTER seeding for speed.
CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding
    ON document_chunks
    USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_document_chunks_doc_id
    ON document_chunks (doc_id);
