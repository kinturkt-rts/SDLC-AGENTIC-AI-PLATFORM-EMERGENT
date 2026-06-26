-- Migration 005: Create completion_records table
-- Schema: training_compliance

CREATE TABLE IF NOT EXISTS training_compliance.completion_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID NOT NULL REFERENCES training_compliance.employees(id),
    course_id UUID NOT NULL REFERENCES training_compliance.courses(id),
    completion_date DATE NOT NULL,
    expiry_date DATE NULL,
    is_active_record BOOLEAN NOT NULL DEFAULT true,
    superseded_by_id UUID NULL REFERENCES training_compliance.completion_records(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_completion_records_emp_course_active
    ON training_compliance.completion_records (employee_id, course_id, is_active_record);
