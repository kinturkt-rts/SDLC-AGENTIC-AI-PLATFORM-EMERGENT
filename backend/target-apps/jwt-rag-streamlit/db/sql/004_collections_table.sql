-- 004_collections_table.sql
SET search_path TO jwt_rag_streamlit, public;

CREATE TABLE IF NOT EXISTS jwt_rag_streamlit.collections (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,
    owner_id INTEGER NOT NULL REFERENCES jwt_rag_streamlit.users(id) ON DELETE CASCADE,
    archived BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_collections_owner ON jwt_rag_streamlit.collections (owner_id);
CREATE INDEX IF NOT EXISTS idx_collections_archived ON jwt_rag_streamlit.collections (archived);
CREATE INDEX IF NOT EXISTS idx_collections_name ON jwt_rag_streamlit.collections (name);
CREATE INDEX IF NOT EXISTS idx_collections_created_at ON jwt_rag_streamlit.collections (created_at);