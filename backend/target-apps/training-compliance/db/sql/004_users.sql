-- Migration 004: Create users table
-- Schema: training_compliance
-- Note: employee_id FK added in 005 after employees table exists (circular reference)

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE t.typname = 'user_role' AND n.nspname = current_schema()
    ) THEN
        CREATE TYPE user_role AS ENUM ('hr_admin', 'manager', 'employee', 'compliance_officer');
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    role user_role NOT NULL,
    employee_id UUID
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);
