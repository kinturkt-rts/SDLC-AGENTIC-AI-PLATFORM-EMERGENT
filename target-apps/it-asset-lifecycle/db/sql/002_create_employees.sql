-- 002_create_employees.sql
-- Creates the employees table with self-referential manager FK

SET search_path TO it_asset_lifecycle, public;

CREATE TABLE IF NOT EXISTS it_asset_lifecycle.employees (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name       VARCHAR(200) NOT NULL,
    email           VARCHAR(255) NOT NULL,
    department      VARCHAR(64) NOT NULL,
    manager_id      UUID REFERENCES it_asset_lifecycle.employees(id),
    is_active       BOOLEAN NOT NULL DEFAULT true,
    deactivated_at  TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_employees_email UNIQUE (email)
);

CREATE INDEX IF NOT EXISTS idx_employees_is_active
    ON it_asset_lifecycle.employees (is_active);
