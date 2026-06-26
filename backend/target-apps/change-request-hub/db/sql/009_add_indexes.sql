-- 009_add_indexes.sql
-- Additional composite indexes for dashboard queries
SET search_path TO change_request_hub;

-- Dashboard: overdue scheduled (planned_end filter + status filter)
CREATE INDEX IF NOT EXISTS idx_change_requests_status_planned_end
    ON change_requests (status, planned_end);

-- Dashboard: monthly by environment
CREATE INDEX IF NOT EXISTS idx_change_requests_env_created
    ON change_requests (target_environment_id, created_at);

-- Dashboard: emergency active
CREATE INDEX IF NOT EXISTS idx_change_requests_type_status
    ON change_requests (change_type, status);
