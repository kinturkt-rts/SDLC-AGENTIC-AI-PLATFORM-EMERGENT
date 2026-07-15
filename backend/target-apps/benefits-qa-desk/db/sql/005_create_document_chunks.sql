-- 005_create_document_chunks.sql
-- Document chunks with pgvector embeddings for RAG retrieval

CREATE TABLE IF NOT EXISTS document_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    embedding vector(1024)
);

CREATE INDEX IF NOT EXISTS idx_document_chunks_document_id ON document_chunks (document_id);

-- HNSW index for cosine similarity search on embeddings
CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding_hnsw
    ON document_chunks USING hnsw (embedding vector_cosine_ops);
