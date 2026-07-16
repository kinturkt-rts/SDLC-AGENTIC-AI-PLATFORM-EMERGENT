-- Migration 006: Create completion_records table
-- Schema: training_compliance

CREATE TABLE IF NOT EXISTS completion_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID NOT NULL REFERENCES employees(id),
    course_id UUID NOT NULL REFERENCES courses(id),
    completion_date DATE NOT NULL,
    expiry_date DATE,
    is_superseded BOOLEAN NOT NULL DEFAULT false,
    recorded_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_completion_records_emp_course_superseded
    ON completion_records (employee_id, course_id, is_superseded);
