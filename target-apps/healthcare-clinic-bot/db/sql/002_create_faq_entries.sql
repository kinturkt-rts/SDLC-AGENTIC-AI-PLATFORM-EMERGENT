-- 002_create_faq_entries.sql
-- Idempotent: creates faq_entries table

CREATE TABLE IF NOT EXISTS healthcare_clinic_bot.faq_entries (
    id SERIAL PRIMARY KEY,
    category VARCHAR(60) NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    search_vector TSVECTOR,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
