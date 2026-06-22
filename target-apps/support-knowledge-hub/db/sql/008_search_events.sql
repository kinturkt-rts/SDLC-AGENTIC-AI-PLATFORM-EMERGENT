-- 008_search_events.sql
SET search_path TO support_knowledge_hub, public;

CREATE TABLE IF NOT EXISTS search_events (
    id                 UUID PRIMARY KEY,
    query_text         TEXT NOT NULL,
    query_embedding    vector(384),
    result_article_ids UUID[] DEFAULT '{}',
    result_count       INT NOT NULL DEFAULT 0,
    role               TEXT NOT NULL,
    timestamp          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_search_events_timestamp ON search_events (timestamp);
