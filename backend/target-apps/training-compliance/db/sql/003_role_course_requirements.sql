-- Migration 003: Create role_course_requirements table
-- Schema: training_compliance

CREATE TABLE IF NOT EXISTS role_course_requirements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_role_id UUID NOT NULL REFERENCES job_roles(id),
    course_id UUID NOT NULL REFERENCES courses(id),
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (job_role_id, course_id)
);
