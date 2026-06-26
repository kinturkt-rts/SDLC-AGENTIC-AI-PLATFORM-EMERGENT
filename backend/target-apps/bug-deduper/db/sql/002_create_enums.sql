-- 002_create_enums.sql
-- Create custom enum types for bug status and API key tier

CREATE SCHEMA IF NOT EXISTS bug_deduper;
SET search_path TO bug_deduper, public;

DO $$ BEGIN
    CREATE TYPE bug_deduper.bug_status AS ENUM ('open', 'resolved', 'closed', 'duplicate');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE bug_deduper.key_tier AS ENUM ('standard', 'admin');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
