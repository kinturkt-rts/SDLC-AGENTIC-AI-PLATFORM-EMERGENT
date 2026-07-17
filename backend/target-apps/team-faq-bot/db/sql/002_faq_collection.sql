-- 002_faq_collection.sql
-- Table: faq_collection — stores uploaded FAQ files (one active at a time)

CREATE TABLE IF NOT EXISTS faq_collection (
    id SERIAL PRIMARY KEY,
    filename TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    char_count INT NOT NULL,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_active BOOLEAN NOT NULL DEFAULT true
);

CREATE INDEX IF NOT EXISTS idx_faq_active ON faq_collection (is_active);
