-- 005_collection_memberships_table.sql
SET search_path TO jwt_rag_streamlit, public;

CREATE TABLE IF NOT EXISTS jwt_rag_streamlit.collection_memberships (
    id SERIAL PRIMARY KEY,
    collection_id INTEGER NOT NULL REFERENCES jwt_rag_streamlit.collections(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES jwt_rag_streamlit.users(id) ON DELETE CASCADE,
    role jwt_rag_streamlit.collection_member_role NOT NULL DEFAULT 'viewer',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Unique constraint to prevent duplicate memberships
    UNIQUE(collection_id, user_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_memberships_collection ON jwt_rag_streamlit.collection_memberships (collection_id);
CREATE INDEX IF NOT EXISTS idx_memberships_user ON jwt_rag_streamlit.collection_memberships (user_id);
CREATE INDEX IF NOT EXISTS idx_memberships_role ON jwt_rag_streamlit.collection_memberships (role);
CREATE INDEX IF NOT EXISTS idx_memberships_created_at ON jwt_rag_streamlit.collection_memberships (created_at);