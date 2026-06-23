-- 001_schema.sql
-- Creates schema, tables, and indexes for gitlab-pipeline-smoke (Team Notice Board API)
-- Idempotent: safe to run multiple times.

SET search_path TO gitlab_pipeline_smoke;

-- ─── Schema ──────────────────────────────────────────────────────────────────
CREATE SCHEMA IF NOT EXISTS gitlab_pipeline_smoke;

SET search_path TO gitlab_pipeline_smoke;

-- ─── categories ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS gitlab_pipeline_smoke.categories (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT        NOT NULL,
    description TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT  uq_categories_name UNIQUE (name)
);

-- ─── notices ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS gitlab_pipeline_smoke.notices (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    category_id  UUID        NOT NULL
                             REFERENCES gitlab_pipeline_smoke.categories(id)
                             ON DELETE RESTRICT,
    title        TEXT        NOT NULL,
    body         TEXT        NOT NULL,
    author_name  TEXT        NOT NULL,
    starts_at    TIMESTAMPTZ,
    ends_at      TIMESTAMPTZ,
    is_archived  BOOLEAN     NOT NULL DEFAULT false,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ─── Indexes ─────────────────────────────────────────────────────────────────
-- Composite index for the active-filter query (is_archived=false, starts_at DESC)
CREATE INDEX IF NOT EXISTS idx_notices_archived_starts
    ON gitlab_pipeline_smoke.notices (is_archived, starts_at DESC);
