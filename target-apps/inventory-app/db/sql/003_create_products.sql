-- 003_create_products.sql
-- Inventory Desk: products table. ON DELETE RESTRICT from categories.
SET search_path TO inventory_app;

CREATE TABLE IF NOT EXISTS inventory_app.products (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    category_id  uuid NOT NULL,
    sku          text NOT NULL,
    name         varchar(120) NOT NULL,
    unit_price   numeric(10, 2) NOT NULL DEFAULT 0,
    qty_on_hand  integer NOT NULL DEFAULT 0,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT products_sku_key UNIQUE (sku),
    CONSTRAINT products_unit_price_nonneg_ck CHECK (unit_price >= 0),
    CONSTRAINT products_qty_on_hand_nonneg_ck CHECK (qty_on_hand >= 0),
    CONSTRAINT products_name_len_ck CHECK (char_length(name) BETWEEN 1 AND 120),
    CONSTRAINT products_category_fk
        FOREIGN KEY (category_id)
        REFERENCES inventory_app.categories (id)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS ix_products_category_id ON inventory_app.products (category_id);
CREATE INDEX IF NOT EXISTS ix_products_sku         ON inventory_app.products (sku);
