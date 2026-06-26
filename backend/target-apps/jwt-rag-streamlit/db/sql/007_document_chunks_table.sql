-- 007_document_chunks_table.sql
SET search_path TO jwt_rag_streamlit, public;

CREATE TABLE IF NOT EXISTS jwt_rag_streamlit.document_chunks (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES jwt_rag_streamlit.documents(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    embedding vector(1024),  -- Amazon Bedrock Titan Embed v2 produces 1024-dimension vectors
    page_number INTEGER,
    chunk_index INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- HNSW index for vector similarity search (after pgvector extension is enabled)
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON jwt_rag_streamlit.document_chunks USING hnsw (embedding vector_cosine_ops);

-- Regular indexes for performance
CREATE INDEX IF NOT EXISTS idx_chunks_document ON jwt_rag_streamlit.document_chunks (document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_page ON jwt_rag_streamlit.document_chunks (page_number);
CREATE INDEX IF NOT EXISTS idx_chunks_chunk_index ON jwt_rag_streamlit.document_chunks (chunk_index);
CREATE INDEX IF NOT EXISTS idx_chunks_created_at ON jwt_rag_streamlit.document_chunks (created_at);