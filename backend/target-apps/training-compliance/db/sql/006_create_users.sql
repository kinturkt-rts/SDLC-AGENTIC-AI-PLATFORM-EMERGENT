-- Migration 006: Create users table
-- Schema: training_compliance

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON t.typnamespace = n.oid
                   WHERE t.typname = 'user_role' AND n.nspname = 'training_compliance') THEN
        CREATE TYPE training_compliance.user_role AS ENUM ('hr_admin', 'manager', 'employee', 'compliance_officer');
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS training_compliance.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID NULL REFERENCES training_compliance.employees(id),
    email TEXT UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    role training_compliance.user_role NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_users_email
    ON training_compliance.users (email);
