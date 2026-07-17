-- 006_create_part_line_items.sql
-- Part line items table for Field Service Dispatch

CREATE TABLE IF NOT EXISTS part_line_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    work_order_id UUID NOT NULL REFERENCES work_orders(id),
    name TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity >= 1),
    unit_cost NUMERIC(10, 2),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_part_line_items_work_order_id ON part_line_items (work_order_id);
