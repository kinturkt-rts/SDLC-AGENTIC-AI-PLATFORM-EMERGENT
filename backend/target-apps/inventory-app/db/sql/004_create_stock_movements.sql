-- 004_create_stock_movements.sql
-- Inventory Desk: stock_movements (immutable audit). CASCADE from products.
SET search_path TO inventory_app;

CREATE TABLE IF NOT EXISTS inventory_app.stock_movements (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id    uuid NOT NULL,
    delta         integer NOT NULL,
    reason        inventory_app.movement_reason NOT NULL,
    note          varchar(500),
    performed_by  uuid,
    created_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT stock_movements_product_fk
        FOREIGN KEY (product_id)
        REFERENCES inventory_app.products (id)
        ON DELETE CASCADE,
    CONSTRAINT stock_movements_user_fk
        FOREIGN KEY (performed_by)
        REFERENCES inventory_app.users (id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_stock_movements_product_id
    ON inventory_app.stock_movements (product_id);

CREATE INDEX IF NOT EXISTS ix_stock_movements_created_at_desc
    ON inventory_app.stock_movements (created_at DESC);

CREATE INDEX IF NOT EXISTS ix_stock_movements_product_created
    ON inventory_app.stock_movements (product_id, created_at DESC);
