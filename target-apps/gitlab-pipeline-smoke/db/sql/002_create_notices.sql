-- 002_create_notices.sql
-- Create notices table with foreign key to categories

SET search_path TO gitlab_pipeline_smoke, public;

-- Create notices table
CREATE TABLE IF NOT EXISTS gitlab_pipeline_smoke.notices (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    category_id uuid NOT NULL,
    title text NOT NULL,
    body text NOT NULL,
    author_name text NOT NULL,
    starts_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ends_at timestamptz NOT NULL,
    is_archived boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Add foreign key constraint to categories
DO $$ BEGIN
    ALTER TABLE gitlab_pipeline_smoke.notices
        ADD CONSTRAINT fk_notices_category_id
        FOREIGN KEY (category_id) REFERENCES gitlab_pipeline_smoke.categories(id)
        ON DELETE RESTRICT;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- Add field length constraints
DO $$ BEGIN
    ALTER TABLE gitlab_pipeline_smoke.notices
        ADD CONSTRAINT notices_title_length CHECK (length(title) >= 1 AND length(title) <= 120);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE gitlab_pipeline_smoke.notices
        ADD CONSTRAINT notices_body_length CHECK (length(body) >= 1 AND length(body) <= 4000);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE gitlab_pipeline_smoke.notices
        ADD CONSTRAINT notices_author_name_length CHECK (length(author_name) >= 1 AND length(author_name) <= 80);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- Add date validation constraint
DO $$ BEGIN
    ALTER TABLE gitlab_pipeline_smoke.notices
        ADD CONSTRAINT notices_date_order CHECK (ends_at >= starts_at);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- Create indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_notices_category_id 
    ON gitlab_pipeline_smoke.notices (category_id);

CREATE INDEX IF NOT EXISTS idx_notices_starts_at 
    ON gitlab_pipeline_smoke.notices (starts_at);

CREATE INDEX IF NOT EXISTS idx_notices_ends_at 
    ON gitlab_pipeline_smoke.notices (ends_at);

CREATE INDEX IF NOT EXISTS idx_notices_is_archived 
    ON gitlab_pipeline_smoke.notices (is_archived);

-- Composite index for active notice queries
CREATE INDEX IF NOT EXISTS idx_notices_active_filter 
    ON gitlab_pipeline_smoke.notices (is_archived, starts_at, ends_at);

-- Index for text search on title and body (ILIKE; no pg_trgm required for MVP)
CREATE INDEX IF NOT EXISTS idx_notices_title_lower
    ON gitlab_pipeline_smoke.notices (lower(title));

CREATE INDEX IF NOT EXISTS idx_notices_body_lower
    ON gitlab_pipeline_smoke.notices (lower(body));