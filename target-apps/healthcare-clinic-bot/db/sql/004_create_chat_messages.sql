-- 004_create_chat_messages.sql
-- Idempotent: creates chat_messages table

CREATE TABLE IF NOT EXISTS healthcare_clinic_bot.chat_messages (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES healthcare_clinic_bot.chat_sessions(id) ON DELETE CASCADE,
    role VARCHAR(10) NOT NULL,
    content TEXT NOT NULL,
    is_fallback BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_messages_role CHECK (role IN ('user', 'assistant'))
);

CREATE INDEX IF NOT EXISTS idx_msgs_session_id
    ON healthcare_clinic_bot.chat_messages (session_id);
