-- Migration 003: Create employees table
-- Schema: training_compliance

CREATE TABLE IF NOT EXISTS training_compliance.employees (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    department_id UUID NOT NULL REFERENCES training_compliance.departments(id),
    job_role_id UUID NOT NULL REFERENCES training_compliance.job_roles(id),
    manager_id UUID NULL REFERENCES training_compliance.employees(id),
    is_active BOOLEAN NOT NULL DEFAULT true
);

CREATE INDEX IF NOT EXISTS idx_employees_manager_id
    ON training_compliance.employees (manager_id);

CREATE INDEX IF NOT EXISTS idx_employees_is_active
    ON training_compliance.employees (is_active);

CREATE INDEX IF NOT EXISTS idx_employees_job_role_id
    ON training_compliance.employees (job_role_id);
