-- 001_enable_pgvector.sql
-- Enable pgvector extension in public schema for vector similarity search
CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;
