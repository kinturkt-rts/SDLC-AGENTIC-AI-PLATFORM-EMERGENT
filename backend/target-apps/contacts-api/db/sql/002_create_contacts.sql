-- 002_create_contacts.sql
-- Creates the contacts table per design §3

CREATE TABLE IF NOT EXISTS contacts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    department_id uuid NOT NULL REFERENCES departments(id) ON DELETE RESTRICT,
    full_name text NOT NULL,
    email text UNIQUE NOT NULL,
    phone text,
    title text,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_contacts_full_name_length CHECK (length(full_name) <= 120)
);

CREATE INDEX IF NOT EXISTS idx_contacts_department_id ON contacts(department_id);
CREATE INDEX IF NOT EXISTS idx_contacts_is_active ON contacts(is_active);
