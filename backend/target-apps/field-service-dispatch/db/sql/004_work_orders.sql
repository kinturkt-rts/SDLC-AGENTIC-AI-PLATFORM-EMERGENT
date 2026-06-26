-- Migration 004: work_orders table
-- Schema: field_service_dispatch

CREATE TABLE IF NOT EXISTS field_service_dispatch.work_orders (
    id UUID PRIMARY KEY,
    customer_id UUID NOT NULL REFERENCES field_service_dispatch.customers(id),
    description TEXT NOT NULL,
    priority TEXT NOT NULL CHECK (priority IN ('routine', 'urgent')),
    scheduled_date DATE NOT NULL,
    time_window TEXT NOT NULL CHECK (time_window IN ('morning', 'afternoon', 'all_day')),
    status TEXT NOT NULL CHECK (status IN ('new', 'assigned', 'in_progress', 'completed', 'cancelled'))
        DEFAULT 'new',
    assigned_technician_id UUID NULL REFERENCES field_service_dispatch.technicians(id),
    completion_notes TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_work_orders_scheduled_status
    ON field_service_dispatch.work_orders (scheduled_date, status);

CREATE INDEX IF NOT EXISTS idx_work_orders_assigned_technician
    ON field_service_dispatch.work_orders (assigned_technician_id);
