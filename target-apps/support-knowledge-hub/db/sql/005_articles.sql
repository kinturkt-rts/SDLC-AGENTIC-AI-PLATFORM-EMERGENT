-- 005_articles.sql
SET search_path TO support_knowledge_hub, public;

CREATE TABLE IF NOT EXISTS articles (
    id           UUID PRIMARY KEY,
    title        TEXT NOT NULL,
    body         TEXT NOT NULL,
    category_id  UUID NOT NULL REFERENCES categories(id),
    tags         TEXT[] DEFAULT '{}',
    author_id    UUID NOT NULL REFERENCES users(id),
    status       TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','published','archived')),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_at TIMESTAMPTZ,
    archived_at  TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_articles_status_category ON articles (status, category_id);
