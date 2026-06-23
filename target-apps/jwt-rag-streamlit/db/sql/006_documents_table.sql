-- 006_documents_table.sql
SET search_path TO jwt_rag_streamlit, public;

CREATE TABLE IF NOT EXISTS jwt_rag_streamlit.documents (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    collection_id INTEGER NOT NULL REFERENCES jwt_rag_streamlit.collections(id) ON DELETE CASCADE,
    status jwt_rag_streamlit.document_status NOT NULL DEFAULT 'pending',
    uploaded_by INTEGER NOT NULL REFERENCES jwt_rag_streamlit.users(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_documents_collection ON jwt_rag_streamlit.documents (collection_id);
CREATE INDEX IF NOT EXISTS idx_documents_status ON jwt_rag_streamlit.documents (status);
CREATE INDEX IF NOT EXISTS idx_documents_uploaded_by ON jwt_rag_streamlit.documents (uploaded_by);
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON jwt_rag_streamlit.documents (created_at);
CREATE INDEX IF NOT EXISTS idx_documents_title ON jwt_rag_streamlit.documents (title);