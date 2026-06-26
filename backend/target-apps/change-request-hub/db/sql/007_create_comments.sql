-- 007_create_comments.sql
SET search_path TO change_request_hub;

CREATE TABLE IF NOT EXISTS comments (
    id UUID PRIMARY KEY,
    change_id UUID NOT NULL REFERENCES change_requests(id),
    author_id UUID NOT NULL REFERENCES users(id),
    body TEXT NOT NULL,
    posted_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_comments_change ON comments (change_id);
