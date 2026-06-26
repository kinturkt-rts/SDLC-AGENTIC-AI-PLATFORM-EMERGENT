-- 006_search_logs_and_items.sql
SET search_path TO support_knowledge_hub, public;

CREATE TABLE IF NOT EXISTS search_logs (
    id              uuid PRIMARY KEY,
    user_id_hash    text NOT NULL,
    query_text      text NOT NULL,
    category_filter uuid REFERENCES categories(id),
    result_count    int NOT NULL DEFAULT 0,
    executed_at     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_search_logs_executed_at ON search_logs (executed_at);

CREATE TABLE IF NOT EXISTS search_result_items (
    id              uuid PRIMARY KEY,
    search_log_id   uuid NOT NULL REFERENCES search_logs(id) ON DELETE CASCADE,
    article_id      uuid NOT NULL REFERENCES articles(id),
    rank_position   int NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_search_result_items_search_log_id ON search_result_items (search_log_id);
