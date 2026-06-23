-- 010_audit_log_table.sql
SET search_path TO jwt_rag_streamlit, public;

CREATE TABLE IF NOT EXISTS jwt_rag_streamlit.audit_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES jwt_rag_streamlit.users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50),
    resource_id INTEGER,
    details JSONB,
    ip_address INET,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance and audit queries
CREATE INDEX IF NOT EXISTS idx_audit_user_action ON jwt_rag_streamlit.audit_log (user_id, action);
CREATE INDEX IF NOT EXISTS idx_audit_created_at ON jwt_rag_streamlit.audit_log (created_at);
CREATE INDEX IF NOT EXISTS idx_audit_action ON jwt_rag_streamlit.audit_log (action);
CREATE INDEX IF NOT EXISTS idx_audit_resource ON jwt_rag_streamlit.audit_log (resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_audit_ip ON jwt_rag_streamlit.audit_log (ip_address);

-- GIN index for JSONB details column for efficient querying
CREATE INDEX IF NOT EXISTS idx_audit_details ON jwt_rag_streamlit.audit_log USING gin (details);