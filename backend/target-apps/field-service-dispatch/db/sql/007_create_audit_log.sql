-- 007_create_audit_log.sql
-- Audit log table for Field Service Dispatch (append-only)

CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    work_order_id UUID NOT NULL REFERENCES work_orders(id),
    from_status TEXT,
    to_status TEXT NOT NULL,
    actor_id UUID NOT NULL REFERENCES users(id),
    actor_role TEXT NOT NULL,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_log_work_order_id ON audit_log (work_order_id);
