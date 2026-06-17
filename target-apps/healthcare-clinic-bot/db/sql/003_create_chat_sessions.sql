-- 003_create_chat_sessions.sql
-- Idempotent: creates chat_sessions table

CREATE TABLE IF NOT EXISTS healthcare_clinic_bot.chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_label VARCHAR(120),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_sessions_created
    ON healthcare_clinic_bot.chat_sessions (created_at);
