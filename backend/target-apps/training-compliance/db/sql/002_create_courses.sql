-- Migration 002: Create courses table
-- Schema: training_compliance

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON t.typnamespace = n.oid
                   WHERE t.typname = 'course_category' AND n.nspname = 'training_compliance') THEN
        CREATE TYPE training_compliance.course_category AS ENUM ('safety', 'security', 'role_specific');
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS training_compliance.courses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE NOT NULL,
    category training_compliance.course_category NOT NULL,
    validity_period_months INT NULL,
    required_for_all_staff BOOLEAN NOT NULL DEFAULT false,
    certificate_ref TEXT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true
);

CREATE INDEX IF NOT EXISTS idx_courses_is_active
    ON training_compliance.courses (is_active);
