-- 003_faq_chunks.sql
-- Table: faq_chunks — chunked FAQ content with embedding vectors for similarity search

CREATE TABLE IF NOT EXISTS faq_chunks (
    id SERIAL PRIMARY KEY,
    collection_id INT NOT NULL REFERENCES faq_collection(id),
    heading TEXT,
    chunk_text TEXT NOT NULL,
    embedding vector(1024) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chunks_collection ON faq_chunks (collection_id);

-- HNSW index for cosine similarity search
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON faq_chunks USING hnsw (embedding vector_cosine_ops);
