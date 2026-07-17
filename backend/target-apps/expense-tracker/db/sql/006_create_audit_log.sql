-- 006_create_audit_log.sql
-- Audit log table (FR-5, NFR-8)

CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    expense_id INT NOT NULL REFERENCES expenses(id),
    from_status VARCHAR(20),
    to_status VARCHAR(20) NOT NULL,
    actor_id INT NOT NULL,
    actor_role VARCHAR(20) NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
