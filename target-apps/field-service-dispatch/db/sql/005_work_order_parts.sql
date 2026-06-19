-- Migration 005: work_order_parts table
-- Schema: field_service_dispatch

CREATE TABLE IF NOT EXISTS field_service_dispatch.work_order_parts (
    id UUID PRIMARY KEY,
    work_order_id UUID NOT NULL REFERENCES field_service_dispatch.work_orders(id),
    part_name TEXT NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    unit_cost NUMERIC(10,2) NULL
);

CREATE INDEX IF NOT EXISTS idx_work_order_parts_work_order_id
    ON field_service_dispatch.work_order_parts (work_order_id);
