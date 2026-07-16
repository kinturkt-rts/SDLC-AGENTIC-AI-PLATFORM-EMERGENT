-- 004_create_work_orders.sql
-- Work orders table for Field Service Dispatch

CREATE TABLE IF NOT EXISTS work_orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES customers(id),
    description TEXT NOT NULL,
    priority TEXT NOT NULL CHECK (priority IN ('routine', 'urgent')),
    scheduled_date DATE NOT NULL,
    time_window TEXT NOT NULL CHECK (time_window IN ('morning', 'afternoon', 'all_day')),
    status TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'assigned', 'in_progress', 'completed', 'cancelled')),
    completion_notes TEXT,
    dispatcher_addendum TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_work_orders_scheduled_status ON work_orders (scheduled_date, status);
CREATE INDEX IF NOT EXISTS idx_work_orders_status ON work_orders (status);
