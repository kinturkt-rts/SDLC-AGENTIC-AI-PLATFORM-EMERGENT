-- Clean dev re-apply when prior partial runs left mismatched types (e.g. uuid vs serial)
DROP SCHEMA IF EXISTS notice_board_ui CASCADE;
CREATE SCHEMA notice_board_ui;
SET search_path TO notice_board_ui;

-- Categories table for organizing notices
CREATE TABLE IF NOT EXISTS categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for category name lookups
CREATE INDEX IF NOT EXISTS idx_categories_name ON categories(name);