-- 005_create_expenses.sql
-- Expenses table (FR-1, FR-2, FR-3, FR-4, FR-8)

CREATE TABLE IF NOT EXISTS expenses (
    id SERIAL PRIMARY KEY,
    employee_id INT NOT NULL REFERENCES employees(id),
    team_id INT NOT NULL REFERENCES teams(id),
    original_amount NUMERIC(19,4) NOT NULL,
    currency CHAR(3) NOT NULL,
    usd_amount NUMERIC(19,4) NOT NULL,
    category VARCHAR(20) NOT NULL,
    description VARCHAR(500),
    expense_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'submitted',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ
);
