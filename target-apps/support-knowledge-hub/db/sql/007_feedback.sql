-- 007_feedback.sql
SET search_path TO support_knowledge_hub, public;

CREATE TABLE IF NOT EXISTS feedback (
    id              uuid PRIMARY KEY,
    search_log_id   uuid NOT NULL REFERENCES search_logs(id),
    article_id      uuid NOT NULL REFERENCES articles(id),
    user_id_hash    text NOT NULL,
    signal          text NOT NULL CHECK (signal IN ('helpful','not_helpful')),
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (search_log_id, article_id, user_id_hash)
);
