-- 001_create_enum_types.sql
-- Create schema and enum types for shift_swap_board

CREATE SCHEMA IF NOT EXISTS shift_swap_board;
SET search_path = shift_swap_board;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_role' AND typnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'shift_swap_board')) THEN
        CREATE TYPE shift_swap_board.user_role AS ENUM ('staff', 'floor_lead', 'admin');
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'shift_window' AND typnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'shift_swap_board')) THEN
        CREATE TYPE shift_swap_board.shift_window AS ENUM ('morning', 'afternoon', 'full');
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'swap_status' AND typnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'shift_swap_board')) THEN
        CREATE TYPE shift_swap_board.swap_status AS ENUM ('open', 'claimed', 'approved', 'denied', 'cancelled');
    END IF;
END $$;
