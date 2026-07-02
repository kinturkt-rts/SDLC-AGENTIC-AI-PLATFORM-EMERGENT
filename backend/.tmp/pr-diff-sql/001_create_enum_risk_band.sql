-- 001_create_enum_risk_band.sql
-- Create risk_band_enum type for the reviews table

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE t.typname = 'risk_band_enum' AND n.nspname = current_schema()
    ) THEN
        CREATE TYPE risk_band_enum AS ENUM ('low', 'medium', 'high');
    END IF;
END $$;
