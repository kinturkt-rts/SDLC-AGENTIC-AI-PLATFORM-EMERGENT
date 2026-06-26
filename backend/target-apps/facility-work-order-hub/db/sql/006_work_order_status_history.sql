-- 006_work_order_status_history.sql
-- Status history audit log (append-only)

SET search_path TO facility_work_order_hub;

CREATE TABLE IF NOT EXISTS work_order_status_history (
    id UUID PRIMARY KEY,
    work_order_id UUID NOT NULL REFERENCES work_orders(id),
    from_status wo_status_enum,
    to_status wo_status_enum NOT NULL,
    changed_by_user_id UUID NOT NULL REFERENCES users(id),
    changed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_wo_status_history_work_order_id ON work_order_status_history (work_order_id);
