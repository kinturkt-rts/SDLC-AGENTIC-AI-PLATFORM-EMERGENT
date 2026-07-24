-- 005_create_expenses.sql
-- Creates the expenses table (FR-1, FR-2, FR-3, FR-4, FR-5)

CREATE TABLE IF NOT EXISTS expenses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    team_id UUID NOT NULL REFERENCES teams(id),
    amount NUMERIC(19,4) NOT NULL,
    currency CHAR(3) NOT NULL,
    amount_usd NUMERIC(19,4) NOT NULL,
    category VARCHAR(20) NOT NULL,
    description VARCHAR(1000),
    expense_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'submitted',
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ
);
