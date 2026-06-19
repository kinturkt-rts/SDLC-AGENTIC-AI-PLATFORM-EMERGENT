-- 001_create_departments.sql
-- Create departments table according to design §3

CREATE TABLE IF NOT EXISTS departments (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name       text NOT NULL,
    code       text NOT NULL UNIQUE,
    created_at timestamp NOT NULL DEFAULT now(),
    
    CONSTRAINT chk_departments_name_length CHECK (length(name) >= 1 AND length(name) <= 80),
    CONSTRAINT chk_departments_code_format CHECK (code ~* '^[A-Z]{2,10}$')
);

-- Create unique index on code for performance
CREATE UNIQUE INDEX IF NOT EXISTS idx_departments_code ON departments (code);