-- 005_create_search_events.sql
-- Search event analytics (no PII)

SET search_path = platform_desk, public;

CREATE TABLE IF NOT EXISTS platform_desk.search_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_text VARCHAR(500) NOT NULL,
    service_filter_id UUID REFERENCES platform_desk.services(id),
    result_count INT NOT NULL,
    top_score FLOAT NOT NULL,
    response_time_ms INT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_search_created
    ON platform_desk.search_events (created_at);
