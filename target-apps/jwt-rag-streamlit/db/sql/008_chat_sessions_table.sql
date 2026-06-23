-- 008_chat_sessions_table.sql
SET search_path TO jwt_rag_streamlit, public;

CREATE TABLE IF NOT EXISTS jwt_rag_streamlit.chat_sessions (
    id SERIAL PRIMARY KEY,
    collection_id INTEGER NOT NULL REFERENCES jwt_rag_streamlit.collections(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES jwt_rag_streamlit.users(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_sessions_user_collection ON jwt_rag_streamlit.chat_sessions (user_id, collection_id);
CREATE INDEX IF NOT EXISTS idx_sessions_collection ON jwt_rag_streamlit.chat_sessions (collection_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON jwt_rag_streamlit.chat_sessions (user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_created_at ON jwt_rag_streamlit.chat_sessions (created_at);