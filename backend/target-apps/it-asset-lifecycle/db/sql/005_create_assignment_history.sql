-- 005_create_assignment_history.sql
-- Append-only audit log for assignment lifecycle events

SET search_path TO it_asset_lifecycle, public;

DO $$ BEGIN
    CREATE TYPE it_asset_lifecycle.assignment_event_type AS ENUM ('assign', 'return');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS it_asset_lifecycle.assignment_history (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id        UUID NOT NULL REFERENCES it_asset_lifecycle.assets(id),
    employee_id     UUID NOT NULL REFERENCES it_asset_lifecycle.employees(id),
    event_type      it_asset_lifecycle.assignment_event_type NOT NULL,
    event_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    actor_id        UUID NOT NULL REFERENCES it_asset_lifecycle.users(id),
    condition_note  TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_assignment_history_asset
    ON it_asset_lifecycle.assignment_history (asset_id);

CREATE INDEX IF NOT EXISTS idx_assignment_history_employee
    ON it_asset_lifecycle.assignment_history (employee_id);
