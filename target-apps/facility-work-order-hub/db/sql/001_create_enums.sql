-- 001_create_enums.sql
-- Create application schema and enum types for Facility Work Order Hub

CREATE SCHEMA IF NOT EXISTS facility_work_order_hub;
SET search_path TO facility_work_order_hub;

DO $$ BEGIN
    CREATE TYPE user_role_enum AS ENUM ('requester', 'technician', 'facilities_admin', 'leadership');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE wo_category_enum AS ENUM ('HVAC', 'plumbing', 'electrical', 'access', 'general');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE wo_priority_enum AS ENUM ('low', 'normal', 'urgent');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE wo_status_enum AS ENUM ('submitted', 'triaged', 'assigned', 'in_progress', 'completed', 'closed');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
