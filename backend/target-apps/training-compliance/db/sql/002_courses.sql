-- Migration 002: Create courses table with enums
-- Schema: training_compliance

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE t.typname = 'course_category' AND n.nspname = current_schema()
    ) THEN
        CREATE TYPE course_category AS ENUM ('safety', 'security', 'role_specific');
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE t.typname = 'course_scope' AND n.nspname = current_schema()
    ) THEN
        CREATE TYPE course_scope AS ENUM ('all_staff', 'role_specific');
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS courses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE NOT NULL,
    category course_category NOT NULL,
    validity_period_months INT,
    scope course_scope NOT NULL DEFAULT 'all_staff',
    reference_field TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_courses_scope ON courses (scope);
