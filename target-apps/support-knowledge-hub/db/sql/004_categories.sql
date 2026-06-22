-- 004_categories.sql
SET search_path TO support_knowledge_hub, public;

CREATE TABLE IF NOT EXISTS categories (
    id          UUID PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    slug        TEXT NOT NULL UNIQUE,
    created_by  UUID NOT NULL REFERENCES users(id),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
