-- Set search path to notice_board_ui schema
SET search_path TO notice_board_ui;

-- Audit log table for tracking organizer operations
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    table_name VARCHAR(50) NOT NULL,
    operation VARCHAR(10) NOT NULL,
    record_id INTEGER NOT NULL,
    organizer_action BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for audit queries by table and record
CREATE INDEX IF NOT EXISTS idx_audit_table_record ON audit_log(table_name, record_id);