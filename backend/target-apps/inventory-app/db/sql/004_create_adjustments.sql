-- 004_create_adjustments.sql
-- Create adjustments table — append-only audit log (FR-5, FR-6)

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE t.typname = 'adjustment_reason' AND n.nspname = current_schema()
    ) THEN
        CREATE TYPE adjustment_reason AS ENUM ('sale', 'restock', 'manual_adjustment');
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS adjustments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id      UUID NOT NULL REFERENCES products(id),
    user_id         UUID NOT NULL REFERENCES users(id),
    delta           INTEGER NOT NULL,
    reason          adjustment_reason NOT NULL,
    note            TEXT,
    quantity_after   INTEGER NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_adjustments_product_created
    ON adjustments (product_id, created_at);
