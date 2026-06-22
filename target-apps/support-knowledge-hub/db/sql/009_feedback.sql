-- 009_feedback.sql
SET search_path TO support_knowledge_hub, public;

CREATE TABLE IF NOT EXISTS feedback (
    id              UUID PRIMARY KEY,
    search_event_id UUID NOT NULL REFERENCES search_events(id),
    article_id      UUID NOT NULL REFERENCES articles(id),
    rating          TEXT NOT NULL CHECK (rating IN ('helpful','not_helpful')),
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (search_event_id, article_id)
);
