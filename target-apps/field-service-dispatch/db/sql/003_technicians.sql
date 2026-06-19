-- Migration 003: technicians table
-- Schema: field_service_dispatch

CREATE TABLE IF NOT EXISTS field_service_dispatch.technicians (
    id UUID PRIMARY KEY,
    display_name TEXT NOT NULL,
    skills TEXT[] NOT NULL DEFAULT '{}',
    is_active BOOLEAN NOT NULL DEFAULT true
);

CREATE INDEX IF NOT EXISTS idx_technicians_is_active
    ON field_service_dispatch.technicians (is_active);

-- Add FK from users.technician_id -> technicians.id now that technicians exists
ALTER TABLE field_service_dispatch.users
    DROP CONSTRAINT IF EXISTS fk_users_technician_id;

ALTER TABLE field_service_dispatch.users
    ADD CONSTRAINT fk_users_technician_id
    FOREIGN KEY (technician_id) REFERENCES field_service_dispatch.technicians(id);
