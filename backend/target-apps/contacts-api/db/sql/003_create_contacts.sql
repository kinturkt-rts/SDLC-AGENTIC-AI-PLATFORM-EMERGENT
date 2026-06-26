-- 003_create_contacts.sql
-- Contacts table within contacts_api schema

SET search_path TO contacts_api;

CREATE TABLE IF NOT EXISTS contacts (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    department_id   uuid        NOT NULL REFERENCES departments(id) ON DELETE RESTRICT,
    full_name       text        NOT NULL,
    email           text        NOT NULL,
    phone           text,
    title           text,
    is_active       boolean     NOT NULL DEFAULT true,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT uq_contacts_email UNIQUE (email)
);

CREATE INDEX IF NOT EXISTS idx_contacts_email ON contacts (email);
CREATE INDEX IF NOT EXISTS idx_contacts_department_id ON contacts (department_id);
CREATE INDEX IF NOT EXISTS idx_contacts_is_active ON contacts (is_active);
