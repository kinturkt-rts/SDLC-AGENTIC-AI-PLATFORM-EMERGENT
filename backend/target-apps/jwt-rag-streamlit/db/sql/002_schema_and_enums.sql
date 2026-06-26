-- 002_schema_and_enums.sql
SET search_path TO jwt_rag_streamlit, public;

-- Create schema if it doesn't exist
CREATE SCHEMA IF NOT EXISTS jwt_rag_streamlit;

-- User role enumeration
CREATE TYPE jwt_rag_streamlit.user_role AS ENUM ('viewer', 'contributor', 'admin');

-- User status enumeration  
CREATE TYPE jwt_rag_streamlit.user_status AS ENUM ('active', 'inactive');

-- Collection membership role enumeration
CREATE TYPE jwt_rag_streamlit.collection_member_role AS ENUM ('viewer', 'contributor');

-- Document status enumeration
CREATE TYPE jwt_rag_streamlit.document_status AS ENUM ('pending', 'processing', 'success', 'failed');