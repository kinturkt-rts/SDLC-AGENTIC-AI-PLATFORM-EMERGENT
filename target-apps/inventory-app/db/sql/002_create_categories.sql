-- 002_create_categories.sql
-- Inventory Desk: categories table.
SET search_path TO inventory_app;

CREATE TABLE IF NOT EXISTS inventory_app.categories (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name        varchar(80) NOT NULL,
    slug        varchar(100) NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT categories_slug_key UNIQUE (slug),
    CONSTRAINT categories_name_len_ck CHECK (char_length(name) BETWEEN 1 AND 80)
);

CREATE INDEX IF NOT EXISTS ix_categories_slug ON inventory_app.categories (slug);
