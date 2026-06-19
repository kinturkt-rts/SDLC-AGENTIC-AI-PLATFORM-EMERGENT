-- 004_create_assignments.sql
-- Creates the assignments table with partial unique index for single active assignment

SET search_path TO it_asset_lifecycle, public;

CREATE TABLE IF NOT EXISTS it_asset_lifecycle.assignments (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id                UUID NOT NULL REFERENCES it_asset_lifecycle.assets(id),
    employee_id             UUID NOT NULL REFERENCES it_asset_lifecycle.employees(id),
    assigned_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    returned_at             TIMESTAMPTZ,
    assigned_by             UUID NOT NULL REFERENCES it_asset_lifecycle.users(id),
    return_condition_note   TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Enforces FR-2: at most one active assignment per non-license asset
CREATE UNIQUE INDEX IF NOT EXISTS uq_assignments_active_asset
    ON it_asset_lifecycle.assignments (asset_id)
    WHERE returned_at IS NULL;
