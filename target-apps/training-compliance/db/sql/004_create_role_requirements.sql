-- Migration 004: Create role_requirements table
-- Schema: training_compliance

CREATE TABLE IF NOT EXISTS training_compliance.role_requirements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_role_id UUID NOT NULL REFERENCES training_compliance.job_roles(id),
    course_id UUID NOT NULL REFERENCES training_compliance.courses(id),
    UNIQUE (job_role_id, course_id)
);
