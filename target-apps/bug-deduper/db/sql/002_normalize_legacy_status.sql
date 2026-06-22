-- Normalize legacy bug_status values from an earlier pipeline schema.
UPDATE bugs
SET status = 'closed'
WHERE status::text = 'resolved';

ALTER TABLE bugs ALTER COLUMN status DROP DEFAULT;

ALTER TABLE bugs
    ALTER COLUMN status TYPE bug_status_enum
    USING (
        CASE status::text
            WHEN 'open' THEN 'open'::bug_status_enum
            WHEN 'closed' THEN 'closed'::bug_status_enum
            WHEN 'duplicate' THEN 'duplicate'::bug_status_enum
            WHEN 'resolved' THEN 'closed'::bug_status_enum
            ELSE 'open'::bug_status_enum
        END
    );

ALTER TABLE bugs ALTER COLUMN status SET DEFAULT 'open'::bug_status_enum;
