-- 006_create_indexes.sql
-- Additional indexes specified in design section 3

SET search_path TO it_asset_lifecycle, public;

CREATE INDEX IF NOT EXISTS idx_assets_warranty_status
    ON it_asset_lifecycle.assets (warranty_end_date, status);

CREATE INDEX IF NOT EXISTS idx_assets_asset_type
    ON it_asset_lifecycle.assets (asset_type);

CREATE INDEX IF NOT EXISTS idx_assets_status
    ON it_asset_lifecycle.assets (status);
