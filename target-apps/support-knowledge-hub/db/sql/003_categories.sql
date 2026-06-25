-- 003_categories.sql
SET search_path TO support_knowledge_hub, public;

CREATE TABLE IF NOT EXISTS categories (
    id          uuid PRIMARY KEY,
    name        text NOT NULL UNIQUE,
    is_active   boolean NOT NULL DEFAULT true,
    created_at  timestamptz NOT NULL DEFAULT now(),
    created_by  uuid REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_categories_is_active ON categories (is_active);
