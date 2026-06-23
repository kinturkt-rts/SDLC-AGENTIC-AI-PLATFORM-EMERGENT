-- 009_chat_messages_table.sql
SET search_path TO jwt_rag_streamlit, public;

CREATE TABLE IF NOT EXISTS jwt_rag_streamlit.chat_messages (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES jwt_rag_streamlit.chat_sessions(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    is_user BOOLEAN NOT NULL,
    confidence_score FLOAT,
    citations JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_messages_session ON jwt_rag_streamlit.chat_messages (session_id);
CREATE INDEX IF NOT EXISTS idx_messages_is_user ON jwt_rag_streamlit.chat_messages (is_user);
CREATE INDEX IF NOT EXISTS idx_messages_confidence ON jwt_rag_streamlit.chat_messages (confidence_score);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON jwt_rag_streamlit.chat_messages (created_at);

-- GIN index for JSONB citations column for efficient querying
CREATE INDEX IF NOT EXISTS idx_messages_citations ON jwt_rag_streamlit.chat_messages USING gin (citations);