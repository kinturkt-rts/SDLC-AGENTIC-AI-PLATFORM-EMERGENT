-- 002_create_contacts.sql
-- Create contacts table according to design §3

CREATE TABLE IF NOT EXISTS contacts (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    department_id uuid NOT NULL,
    full_name     text NOT NULL,
    email         text UNIQUE,
    phone         text,
    title         text,
    is_active     boolean NOT NULL DEFAULT true,
    created_at    timestamp NOT NULL DEFAULT now(),
    updated_at    timestamp NOT NULL DEFAULT now(),
    
    CONSTRAINT fk_contacts_department FOREIGN KEY (department_id) REFERENCES departments(id),
    CONSTRAINT chk_contacts_full_name_length CHECK (length(full_name) >= 1 AND length(full_name) <= 120),
    CONSTRAINT chk_contacts_phone_length CHECK (phone IS NULL OR length(phone) <= 30),
    CONSTRAINT chk_contacts_title_length CHECK (title IS NULL OR length(title) <= 80)
);