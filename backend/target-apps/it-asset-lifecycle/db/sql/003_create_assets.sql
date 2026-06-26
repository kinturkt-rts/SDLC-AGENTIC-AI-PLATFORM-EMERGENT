-- 003_create_assets.sql
-- Creates the assets table with asset_type and status enums

SET search_path TO it_asset_lifecycle, public;

DO $$ BEGIN
    CREATE TYPE it_asset_lifecycle.asset_type AS ENUM ('laptop', 'monitor', 'phone', 'license', 'misc');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE it_asset_lifecycle.asset_status AS ENUM ('in_stock', 'assigned', 'repair', 'retired');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS it_asset_lifecycle.assets (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_type              it_asset_lifecycle.asset_type NOT NULL,
    manufacturer            VARCHAR(200) NOT NULL,
    model                   VARCHAR(200) NOT NULL,
    serial_number           VARCHAR(200),
    license_key_encrypted   TEXT,
    license_key_last4       VARCHAR(4),
    seats_purchased         INTEGER,
    purchase_date           DATE NOT NULL,
    purchase_cost           NUMERIC(12,2) NOT NULL,
    warranty_end_date       DATE,
    status                  it_asset_lifecycle.asset_status NOT NULL DEFAULT 'in_stock',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_assets_serial_number UNIQUE (serial_number)
);
