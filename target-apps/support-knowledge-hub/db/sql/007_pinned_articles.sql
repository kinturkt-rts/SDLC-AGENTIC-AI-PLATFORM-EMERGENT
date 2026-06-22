-- 007_pinned_articles.sql
SET search_path TO support_knowledge_hub, public;

CREATE TABLE IF NOT EXISTS pinned_articles (
    id          UUID PRIMARY KEY,
    category_id UUID NOT NULL REFERENCES categories(id),
    article_id  UUID NOT NULL REFERENCES articles(id),
    pinned_by   UUID NOT NULL REFERENCES users(id),
    pinned_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (category_id, article_id)
);
