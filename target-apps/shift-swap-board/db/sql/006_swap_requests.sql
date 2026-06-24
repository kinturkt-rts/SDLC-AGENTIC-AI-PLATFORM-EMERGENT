-- 006_swap_requests.sql
SET search_path = shift_swap_board;

CREATE TABLE IF NOT EXISTS swap_requests (
    id uuid PRIMARY KEY,
    offered_shift_id uuid NOT NULL REFERENCES shift_roster(id),
    offered_by_user_id uuid NOT NULL REFERENCES users(id),
    status shift_swap_board.swap_status NOT NULL DEFAULT 'open',
    claimed_by_user_id uuid REFERENCES users(id),
    claimed_at timestamptz,
    decided_by_user_id uuid REFERENCES users(id),
    decided_at timestamptz,
    decision_note text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_swap_requests_status ON swap_requests (status);
