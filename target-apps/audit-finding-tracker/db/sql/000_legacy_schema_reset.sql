-- 000_legacy_schema_reset.sql
-- Stale RDS: users table from an older template lacks email/cognito_sub.
-- CREATE TABLE IF NOT EXISTS in 001_users.sql will not add columns — drop and let 001+ recreate.

DO $$
DECLARE
    s text := current_schema();
    legacy_users boolean;
    stale_finding_status boolean;
BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM information_schema.tables t
        WHERE t.table_schema = s AND t.table_name = 'users'
    ) AND NOT EXISTS (
        SELECT 1
        FROM information_schema.columns c
        WHERE c.table_schema = s
          AND c.table_name = 'users'
          AND c.column_name = 'email'
    ) INTO legacy_users;

    SELECT EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE n.nspname = s AND t.typname = 'finding_status'
    ) AND NOT EXISTS (
        SELECT 1
        FROM pg_enum e
        JOIN pg_type t ON t.oid = e.enumtypid
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE n.nspname = s
          AND t.typname = 'finding_status'
          AND e.enumlabel = 'draft'
    ) INTO stale_finding_status;

    IF legacy_users OR stale_finding_status THEN
        DROP TABLE IF EXISTS finding_comments CASCADE;
        DROP TABLE IF EXISTS status_history CASCADE;
        DROP TABLE IF EXISTS evidence_files CASCADE;
        DROP TABLE IF EXISTS findings CASCADE;
        DROP TABLE IF EXISTS audits CASCADE;
        DROP TABLE IF EXISTS users CASCADE;
        DROP TYPE IF EXISTS finding_status CASCADE;
        DROP TYPE IF EXISTS finding_severity CASCADE;
        DROP TYPE IF EXISTS audit_status CASCADE;
        DROP TYPE IF EXISTS user_role CASCADE;
    END IF;
END $$;
