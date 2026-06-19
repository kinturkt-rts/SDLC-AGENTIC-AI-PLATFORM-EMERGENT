-- Migration 006: status_history table (immutable — no UPDATE/DELETE routes)
-- Schema: field_service_dispatch

CREATE TABLE IF NOT EXISTS field_service_dispatch.status_history (
    id UUID PRIMARY KEY,
    work_order_id UUID NOT NULL REFERENCES field_service_dispatch.work_orders(id),
    actor_user_id UUID NOT NULL REFERENCES field_service_dispatch.users(id),
    actor_role TEXT NOT NULL,
    previous_status TEXT NULL,
    new_status TEXT NOT NULL,
    context_note TEXT NULL,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_status_history_wo_changed
    ON field_service_dispatch.status_history (work_order_id, changed_at);
