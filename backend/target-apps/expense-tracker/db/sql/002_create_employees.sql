-- 002_create_employees.sql
-- Employees table (FR-1, FR-3, FR-8, FR-10)

CREATE TABLE IF NOT EXISTS employees (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    team_id INT REFERENCES teams(id),
    token_hash VARCHAR(256) UNIQUE NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'employee',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_employees_token_hash ON employees (token_hash);
