-- 005_create_assignments.sql
-- Assignments table for Field Service Dispatch

CREATE TABLE IF NOT EXISTS assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    work_order_id UUID NOT NULL REFERENCES work_orders(id),
    technician_id UUID NOT NULL REFERENCES technicians(id),
    assigned_by UUID NOT NULL REFERENCES users(id),
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_active BOOLEAN NOT NULL DEFAULT true
);

-- Partial unique index: only one active assignment per work order
CREATE UNIQUE INDEX IF NOT EXISTS idx_assignments_active_work_order
    ON assignments (work_order_id) WHERE is_active = true;
