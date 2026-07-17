-- 007_create_indexes.sql
-- Composite and secondary indexes for query performance (NFR-1, NFR-6)

CREATE INDEX IF NOT EXISTS idx_expenses_team_status_date
    ON expenses (team_id, status, expense_date);

CREATE INDEX IF NOT EXISTS idx_expenses_employee_id
    ON expenses (employee_id);

CREATE INDEX IF NOT EXISTS idx_audit_log_expense_id
    ON audit_log (expense_id);

CREATE INDEX IF NOT EXISTS idx_teams_name
    ON teams (name);
