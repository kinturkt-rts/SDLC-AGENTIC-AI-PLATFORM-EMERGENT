-- 001_create_departments.sql
-- Creates the departments table per design §3

CREATE TABLE IF NOT EXISTS departments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    code text UNIQUE NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_departments_name_length CHECK (length(name) <= 80),
    CONSTRAINT chk_departments_code_format CHECK (code ~ '^[A-Z]{2,10}$')
);
