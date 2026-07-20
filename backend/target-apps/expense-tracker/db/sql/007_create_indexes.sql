-- 007_create_indexes.sql
-- Performance indexes per design §3 and NFR-4

CREATE INDEX IF NOT EXISTS idx_expenses_team_date
    ON expenses(team_id, expense_date, status, deleted_at);

CREATE INDEX IF NOT EXISTS idx_expenses_user
    ON expenses(user_id, status);

CREATE INDEX IF NOT EXISTS idx_audit_expense
    ON audit_log(expense_id, created_at);
