-- 005_work_orders.sql
-- Work orders table

SET search_path TO facility_work_order_hub;

CREATE TABLE IF NOT EXISTS work_orders (
    id UUID PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    category wo_category_enum NOT NULL,
    priority wo_priority_enum NOT NULL,
    status wo_status_enum NOT NULL DEFAULT 'submitted',
    requester_id UUID NOT NULL REFERENCES users(id),
    assignee_id UUID REFERENCES users(id),
    site_id UUID NOT NULL REFERENCES sites(id),
    location_id UUID REFERENCES locations(id),
    due_by TIMESTAMPTZ,
    reopen_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    assigned_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_work_orders_site_id ON work_orders (site_id);
CREATE INDEX IF NOT EXISTS idx_work_orders_assignee_id ON work_orders (assignee_id);
CREATE INDEX IF NOT EXISTS idx_work_orders_status ON work_orders (status);
CREATE INDEX IF NOT EXISTS idx_work_orders_due_by ON work_orders (due_by);
