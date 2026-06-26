-- 001_enable_pgvector.sql
-- Enable pgvector extension for embedding storage and similarity search

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;
