-- 001_create_categories.sql
-- Create gitlab_pipeline_smoke schema and categories table

-- Set search path for this application
SET search_path TO gitlab_pipeline_smoke, public;

-- Create schema if not exists
CREATE SCHEMA IF NOT EXISTS gitlab_pipeline_smoke;

-- Create categories table
CREATE TABLE IF NOT EXISTS gitlab_pipeline_smoke.categories (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL UNIQUE,
    description text,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Add constraints for field lengths
DO $$ BEGIN
    ALTER TABLE gitlab_pipeline_smoke.categories
        ADD CONSTRAINT categories_name_length CHECK (length(name) >= 1 AND length(name) <= 60);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE gitlab_pipeline_smoke.categories
        ADD CONSTRAINT categories_description_length CHECK (description IS NULL OR length(description) <= 240);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- Create unique index on name for fast lookups
CREATE UNIQUE INDEX IF NOT EXISTS idx_categories_name 
    ON gitlab_pipeline_smoke.categories (name);