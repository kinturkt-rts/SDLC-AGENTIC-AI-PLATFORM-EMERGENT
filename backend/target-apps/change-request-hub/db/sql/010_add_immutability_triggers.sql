-- 010_add_immutability_triggers.sql
-- Prevent UPDATE/DELETE on append-only tables
SET search_path TO change_request_hub;

-- Generic deny function
CREATE OR REPLACE FUNCTION deny_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Modifications to this table are not permitted (append-only).';
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- status_history: no UPDATE
DROP TRIGGER IF EXISTS trg_status_history_no_update ON status_history;
CREATE TRIGGER trg_status_history_no_update
    BEFORE UPDATE ON status_history
    FOR EACH ROW EXECUTE FUNCTION deny_modification();

-- status_history: no DELETE
DROP TRIGGER IF EXISTS trg_status_history_no_delete ON status_history;
CREATE TRIGGER trg_status_history_no_delete
    BEFORE DELETE ON status_history
    FOR EACH ROW EXECUTE FUNCTION deny_modification();

-- comments: no UPDATE
DROP TRIGGER IF EXISTS trg_comments_no_update ON comments;
CREATE TRIGGER trg_comments_no_update
    BEFORE UPDATE ON comments
    FOR EACH ROW EXECUTE FUNCTION deny_modification();

-- comments: no DELETE
DROP TRIGGER IF EXISTS trg_comments_no_delete ON comments;
CREATE TRIGGER trg_comments_no_delete
    BEFORE DELETE ON comments
    FOR EACH ROW EXECUTE FUNCTION deny_modification();

-- approval_records: no UPDATE
DROP TRIGGER IF EXISTS trg_approval_records_no_update ON approval_records;
CREATE TRIGGER trg_approval_records_no_update
    BEFORE UPDATE ON approval_records
    FOR EACH ROW EXECUTE FUNCTION deny_modification();

-- approval_records: no DELETE
DROP TRIGGER IF EXISTS trg_approval_records_no_delete ON approval_records;
CREATE TRIGGER trg_approval_records_no_delete
    BEFORE DELETE ON approval_records
    FOR EACH ROW EXECUTE FUNCTION deny_modification();
