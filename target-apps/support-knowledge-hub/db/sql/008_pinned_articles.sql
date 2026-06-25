-- 008_pinned_articles.sql
SET search_path TO support_knowledge_hub, public;

CREATE TABLE IF NOT EXISTS pinned_articles (
    id              uuid PRIMARY KEY,
    category_id     uuid NOT NULL REFERENCES categories(id),
    article_id      uuid NOT NULL REFERENCES articles(id),
    pinned_by       uuid NOT NULL REFERENCES users(id),
    pinned_at       timestamptz NOT NULL DEFAULT now(),
    display_order   int NOT NULL,
    UNIQUE (category_id, article_id)
);
