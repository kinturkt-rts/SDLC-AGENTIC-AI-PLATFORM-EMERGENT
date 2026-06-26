-- 007_comments.sql
-- Comments table (immutable after insert)

SET search_path TO facility_work_order_hub;

CREATE TABLE IF NOT EXISTS comments (
    id UUID PRIMARY KEY,
    work_order_id UUID NOT NULL REFERENCES work_orders(id),
    author_id UUID NOT NULL REFERENCES users(id),
    body TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_comments_work_order_id ON comments (work_order_id);
