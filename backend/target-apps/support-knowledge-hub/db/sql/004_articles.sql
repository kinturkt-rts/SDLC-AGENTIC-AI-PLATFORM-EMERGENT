-- 004_articles.sql
SET search_path TO support_knowledge_hub, public;

CREATE TABLE IF NOT EXISTS articles (
    id              uuid PRIMARY KEY,
    title           text NOT NULL,
    body            text NOT NULL,
    category_id     uuid NOT NULL REFERENCES categories(id),
    tags            text[],
    author_id       uuid NOT NULL REFERENCES users(id),
    state           text NOT NULL DEFAULT 'draft' CHECK (state IN ('draft','published','archived')),
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    published_at    timestamptz,
    archived_at     timestamptz
);

CREATE INDEX IF NOT EXISTS idx_articles_state ON articles (state);
CREATE INDEX IF NOT EXISTS idx_articles_category_id ON articles (category_id);
