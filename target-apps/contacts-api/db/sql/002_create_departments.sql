-- 002_create_departments.sql
-- Departments table within contacts_api schema

SET search_path TO contacts_api;

CREATE TABLE IF NOT EXISTS departments (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    name        text        NOT NULL,
    code        text        NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT uq_departments_code UNIQUE (code),
    CONSTRAINT chk_departments_code_format CHECK (code ~ '^[A-Z]{2,10}$')
);
