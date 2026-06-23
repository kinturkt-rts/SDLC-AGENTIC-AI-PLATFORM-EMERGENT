-- 003_users_table.sql
SET search_path TO jwt_rag_streamlit, public;

CREATE TABLE IF NOT EXISTS jwt_rag_streamlit.users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role jwt_rag_streamlit.user_role NOT NULL DEFAULT 'viewer',
    status jwt_rag_streamlit.user_status NOT NULL DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_users_email ON jwt_rag_streamlit.users (email);
CREATE INDEX IF NOT EXISTS idx_users_role ON jwt_rag_streamlit.users (role);
CREATE INDEX IF NOT EXISTS idx_users_status ON jwt_rag_streamlit.users (status);
CREATE INDEX IF NOT EXISTS idx_users_created_at ON jwt_rag_streamlit.users (created_at);