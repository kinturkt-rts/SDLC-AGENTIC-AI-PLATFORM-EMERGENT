-- 007_swap_audit_log.sql
SET search_path = shift_swap_board;

CREATE TABLE IF NOT EXISTS swap_audit_log (
    id uuid PRIMARY KEY,
    swap_request_id uuid NOT NULL REFERENCES swap_requests(id),
    action varchar(64) NOT NULL,
    actor_user_id uuid NOT NULL REFERENCES users(id),
    detail jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_swap_audit_log_request_created
    ON swap_audit_log (swap_request_id, created_at);
