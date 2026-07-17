-- 004_question_log.sql
-- Table: question_log — anonymised record of each question asked

CREATE TABLE IF NOT EXISTS question_log (
    id SERIAL PRIMARY KEY,
    question_text TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('answered', 'not_in_faq')),
    logged_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_qlog_status_logged ON question_log (status, logged_at);
CREATE INDEX IF NOT EXISTS idx_qlog_expires ON question_log (expires_at);
