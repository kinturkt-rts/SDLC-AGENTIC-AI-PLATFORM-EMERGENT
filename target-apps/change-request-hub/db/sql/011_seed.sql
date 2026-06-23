-- 011_seed.sql
-- Password for all seed users: "ChangeMe123!"
-- DEV/TEST FIXTURE DATA ONLY — not for production use.
SET search_path TO change_request_hub;

-- ============================================================
-- USERS (6): 2 requesters, 2 implementers, 1 manager, 1 leadership
-- ============================================================
INSERT INTO users (id, email, password_hash, display_name, role, active, created_at) VALUES
    ('a1000000-0000-0000-0000-000000000001', 'sam.manager@example.com',     '__BCRYPT_PLACEHOLDER__', 'Sam Chen',        'manager',     true, '2025-01-10 08:00:00+00'),
    ('a1000000-0000-0000-0000-000000000002', 'alice.req@example.com',       '__BCRYPT_PLACEHOLDER__', 'Alice Nguyen',    'requester',   true, '2025-01-10 08:05:00+00'),
    ('a1000000-0000-0000-0000-000000000003', 'bob.req@example.com',         '__BCRYPT_PLACEHOLDER__', 'Bob Martinez',    'requester',   true, '2025-01-10 08:10:00+00'),
    ('a1000000-0000-0000-0000-000000000004', 'charlie.impl@example.com',    '__BCRYPT_PLACEHOLDER__', 'Charlie Davis',   'implementer', true, '2025-01-10 08:15:00+00'),
    ('a1000000-0000-0000-0000-000000000005', 'diana.impl@example.com',      '__BCRYPT_PLACEHOLDER__', 'Diana Park',      'implementer', true, '2025-01-10 08:20:00+00'),
    ('a1000000-0000-0000-0000-000000000006', 'exec.leader@example.com',     '__BCRYPT_PLACEHOLDER__', 'Evan Leadership', 'leadership',  true, '2025-01-10 08:25:00+00')
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- SERVICES (6): 2×tier1, 2×tier2, 2×tier3
-- ============================================================
INSERT INTO services (id, name, owner_team, tier, active, created_at, updated_at) VALUES
    ('b2000000-0000-0000-0000-000000000001', 'Payment Gateway',    'Payments',      'tier1', true, '2025-01-11 09:00:00+00', '2025-01-11 09:00:00+00'),
    ('b2000000-0000-0000-0000-000000000002', 'User Auth Service',  'Identity',      'tier1', true, '2025-01-11 09:05:00+00', '2025-01-11 09:05:00+00'),
    ('b2000000-0000-0000-0000-000000000003', 'Order Processing',   'Commerce',      'tier2', true, '2025-01-11 09:10:00+00', '2025-01-11 09:10:00+00'),
    ('b2000000-0000-0000-0000-000000000004', 'Notification Hub',   'Platform',      'tier2', true, '2025-01-11 09:15:00+00', '2025-01-11 09:15:00+00'),
    ('b2000000-0000-0000-0000-000000000005', 'Internal Wiki',      'Engineering',   'tier3', true, '2025-01-11 09:20:00+00', '2025-01-11 09:20:00+00'),
    ('b2000000-0000-0000-0000-000000000006', 'Dev Sandbox',        'Engineering',   'tier3', true, '2025-01-11 09:25:00+00', '2025-01-11 09:25:00+00')
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- ENVIRONMENTS (3): dev, staging, prod
-- ============================================================
INSERT INTO environments (id, name, sort_order, active, created_at) VALUES
    ('c3000000-0000-0000-0000-000000000001', 'dev',     1, true, '2025-01-12 10:00:00+00'),
    ('c3000000-0000-0000-0000-000000000002', 'staging', 2, true, '2025-01-12 10:05:00+00'),
    ('c3000000-0000-0000-0000-000000000003', 'prod',    3, true, '2025-01-12 10:10:00+00')
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- BLACKOUT WINDOWS (2): 1 active on prod, 1 past on staging
-- ============================================================
INSERT INTO blackout_windows (id, environment_id, start_at, end_at, reason, created_by, created_at) VALUES
    ('d4000000-0000-0000-0000-000000000001', 'c3000000-0000-0000-0000-000000000003', '2025-08-01 00:00:00+00', '2025-08-07 23:59:59+00', 'Q3 code freeze — production stabilisation', 'a1000000-0000-0000-0000-000000000001', '2025-01-15 11:00:00+00'),
    ('d4000000-0000-0000-0000-000000000002', 'c3000000-0000-0000-0000-000000000002', '2025-02-01 00:00:00+00', '2025-02-03 23:59:59+00', 'Staging infra upgrade window',             'a1000000-0000-0000-0000-000000000001', '2025-01-15 11:05:00+00')
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- CHANGE REQUESTS (10): covering all statuses
-- CR-01: draft (standard, low)
-- CR-02: submitted (normal, medium)
-- CR-03: approved (standard, medium)
-- CR-04: rejected (standard, high)
-- CR-05: scheduled — overdue (normal, high) planned_end in past
-- CR-06: scheduled — overdue (standard, medium) planned_end in past
-- CR-07: implementing (normal, medium)
-- CR-08: completed (standard, low)
-- CR-09: closed (normal, low)
-- CR-10: implementing — emergency (emergency, critical)
-- ============================================================
INSERT INTO change_requests (id, title, description, service_id, target_environment_id, change_type, risk, status, requester_id, implementer_id, planned_start, planned_end, rollback_plan, created_at, updated_at, submitted_at, approved_at, scheduled_at, started_at, completed_at, closed_at) VALUES
    -- CR-01: draft
    ('e5000000-0000-0000-0000-000000000001',
     'Add caching layer to Payment Gateway',
     'Introduce Redis caching for frequently accessed payment token lookups to reduce DB load.',
     'b2000000-0000-0000-0000-000000000001', 'c3000000-0000-0000-0000-000000000003',
     'standard', 'low', 'draft',
     'a1000000-0000-0000-0000-000000000002', NULL,
     '2025-04-20 06:00:00+00', '2025-04-20 08:00:00+00',
     'Disable Redis config flag and restart pods.',
     '2025-04-10 14:00:00+00', '2025-04-10 14:00:00+00',
     NULL, NULL, NULL, NULL, NULL, NULL),

    -- CR-02: submitted
    ('e5000000-0000-0000-0000-000000000002',
     'Rotate TLS certificates on Auth Service',
     'Replace expiring TLS certs on auth service load balancer before May deadline.',
     'b2000000-0000-0000-0000-000000000002', 'c3000000-0000-0000-0000-000000000003',
     'normal', 'medium', 'submitted',
     'a1000000-0000-0000-0000-000000000003', NULL,
     '2025-04-25 02:00:00+00', '2025-04-25 04:00:00+00',
     'Re-deploy previous cert bundle from secrets vault.',
     '2025-04-12 09:00:00+00', '2025-04-13 09:00:00+00',
     '2025-04-13 09:00:00+00', NULL, NULL, NULL, NULL, NULL),

    -- CR-03: approved
    ('e5000000-0000-0000-0000-000000000003',
     'Upgrade Order Processing to v3.2',
     'Deploy new version with batch processing improvements and bug fixes.',
     'b2000000-0000-0000-0000-000000000003', 'c3000000-0000-0000-0000-000000000002',
     'standard', 'medium', 'approved',
     'a1000000-0000-0000-0000-000000000002', NULL,
     '2025-04-28 04:00:00+00', '2025-04-28 06:00:00+00',
     'Revert deployment via Helm rollback to v3.1.4.',
     '2025-04-14 10:00:00+00', '2025-04-16 10:00:00+00',
     '2025-04-15 10:00:00+00', '2025-04-16 10:00:00+00', NULL, NULL, NULL, NULL),

    -- CR-04: rejected
    ('e5000000-0000-0000-0000-000000000004',
     'Remove legacy logging from Notification Hub',
     'Strip deprecated log4j config and switch to structured logging.',
     'b2000000-0000-0000-0000-000000000004', 'c3000000-0000-0000-0000-000000000003',
     'standard', 'high', 'rejected',
     'a1000000-0000-0000-0000-000000000003', NULL,
     '2025-03-20 03:00:00+00', '2025-03-20 05:00:00+00',
     'Restore log4j.xml from git history and redeploy.',
     '2025-03-01 11:00:00+00', '2025-03-05 11:00:00+00',
     '2025-03-02 11:00:00+00', NULL, NULL, NULL, NULL, NULL),

    -- CR-05: scheduled — overdue (planned_end in past)
    ('e5000000-0000-0000-0000-000000000005',
     'Database index optimisation on Orders table',
     'Add composite indexes on orders(customer_id, created_at) for reporting queries.',
     'b2000000-0000-0000-0000-000000000003', 'c3000000-0000-0000-0000-000000000003',
     'normal', 'high', 'scheduled',
     'a1000000-0000-0000-0000-000000000002', 'a1000000-0000-0000-0000-000000000004',
     '2025-03-10 02:00:00+00', '2025-03-10 04:00:00+00',
     'Drop newly created indexes if performance degrades.',
     '2025-02-20 08:00:00+00', '2025-03-05 08:00:00+00',
     '2025-02-21 08:00:00+00', '2025-03-01 08:00:00+00', '2025-03-05 08:00:00+00', NULL, NULL, NULL),

    -- CR-06: scheduled — overdue (planned_end in past)
    ('e5000000-0000-0000-0000-000000000006',
     'Wiki search re-indexing',
     'Rebuild Elasticsearch index for Internal Wiki full-text search.',
     'b2000000-0000-0000-0000-000000000005', 'c3000000-0000-0000-0000-000000000001',
     'standard', 'medium', 'scheduled',
     'a1000000-0000-0000-0000-000000000003', 'a1000000-0000-0000-0000-000000000005',
     '2025-03-15 06:00:00+00', '2025-03-15 08:00:00+00',
     'Restore previous index snapshot from S3 backup.',
     '2025-02-25 12:00:00+00', '2025-03-08 12:00:00+00',
     '2025-02-26 12:00:00+00', '2025-03-05 12:00:00+00', '2025-03-08 12:00:00+00', NULL, NULL, NULL),

    -- CR-07: implementing
    ('e5000000-0000-0000-0000-000000000007',
     'Deploy sandbox auto-cleanup cron job',
     'Add daily cron to purge dev sandbox environments older than 7 days.',
     'b2000000-0000-0000-0000-000000000006', 'c3000000-0000-0000-0000-000000000001',
     'normal', 'medium', 'implementing',
     'a1000000-0000-0000-0000-000000000002', 'a1000000-0000-0000-0000-000000000004',
     '2025-04-18 05:00:00+00', '2025-04-18 07:00:00+00',
     'Delete the cron job k8s manifest and re-apply namespace.',
     '2025-04-01 09:00:00+00', '2025-04-17 09:00:00+00',
     '2025-04-02 09:00:00+00', '2025-04-10 09:00:00+00', '2025-04-15 09:00:00+00', '2025-04-17 09:00:00+00', NULL, NULL),

    -- CR-08: completed
    ('e5000000-0000-0000-0000-000000000008',
     'Update Notification Hub email templates',
     'Replace legacy HTML templates with responsive MJML-generated templates.',
     'b2000000-0000-0000-0000-000000000004', 'c3000000-0000-0000-0000-000000000002',
     'standard', 'low', 'completed',
     'a1000000-0000-0000-0000-000000000003', 'a1000000-0000-0000-0000-000000000005',
     '2025-03-25 04:00:00+00', '2025-03-25 06:00:00+00',
     'Revert to previous template directory via git checkout.',
     '2025-03-10 10:00:00+00', '2025-03-26 10:00:00+00',
     '2025-03-11 10:00:00+00', '2025-03-15 10:00:00+00', '2025-03-20 10:00:00+00', '2025-03-24 10:00:00+00', '2025-03-26 10:00:00+00', NULL),

    -- CR-09: closed
    ('e5000000-0000-0000-0000-000000000009',
     'Payment Gateway PCI DSS scan remediation',
     'Patch OpenSSL and disable TLS 1.0/1.1 as flagged in Q1 PCI scan.',
     'b2000000-0000-0000-0000-000000000001', 'c3000000-0000-0000-0000-000000000003',
     'normal', 'low', 'closed',
     'a1000000-0000-0000-0000-000000000002', 'a1000000-0000-0000-0000-000000000004',
     '2025-02-15 02:00:00+00', '2025-02-15 04:00:00+00',
     'Re-enable TLS 1.0 via config if clients fail.',
     '2025-02-01 07:00:00+00', '2025-02-20 07:00:00+00',
     '2025-02-02 07:00:00+00', '2025-02-05 07:00:00+00', '2025-02-10 07:00:00+00', '2025-02-14 07:00:00+00', '2025-02-16 07:00:00+00', '2025-02-20 07:00:00+00'),

    -- CR-10: implementing — emergency
    ('e5000000-0000-0000-0000-000000000010',
     'Emergency hotfix: Auth Service token expiry bug',
     'Tokens issued after 2025-04-14 expire immediately due to clock skew bug in JWT library update.',
     'b2000000-0000-0000-0000-000000000002', 'c3000000-0000-0000-0000-000000000003',
     'emergency', 'critical', 'implementing',
     'a1000000-0000-0000-0000-000000000002', 'a1000000-0000-0000-0000-000000000005',
     '2025-04-15 00:00:00+00', '2025-04-15 02:00:00+00',
     'Pin JWT library to previous version 4.2.1 and redeploy.',
     '2025-04-14 22:00:00+00', '2025-04-15 00:30:00+00',
     '2025-04-14 22:05:00+00', '2025-04-14 23:00:00+00', NULL, '2025-04-15 00:30:00+00', NULL, NULL)
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- APPROVAL RECORDS (6): on CR-03, CR-04(rejected), CR-05, CR-06, CR-07, CR-08, CR-09, CR-10
-- ============================================================
INSERT INTO approval_records (id, change_id, approver_id, decision, comment, decided_at) VALUES
    ('f6000000-0000-0000-0000-000000000001', 'e5000000-0000-0000-0000-000000000003', 'a1000000-0000-0000-0000-000000000001', 'approved', 'Staging deployment approved — low risk.', '2025-04-16 10:00:00+00'),
    ('f6000000-0000-0000-0000-000000000002', 'e5000000-0000-0000-0000-000000000004', 'a1000000-0000-0000-0000-000000000001', 'rejected', 'Insufficient rollback plan. Please add monitoring steps.', '2025-03-05 11:00:00+00'),
    ('f6000000-0000-0000-0000-000000000003', 'e5000000-0000-0000-0000-000000000005', 'a1000000-0000-0000-0000-000000000001', 'approved', 'Index addition is safe; proceed during maintenance window.', '2025-03-01 08:00:00+00'),
    ('f6000000-0000-0000-0000-000000000004', 'e5000000-0000-0000-0000-000000000006', 'a1000000-0000-0000-0000-000000000001', 'approved', 'ES re-index approved for dev.', '2025-03-05 12:00:00+00'),
    ('f6000000-0000-0000-0000-000000000005', 'e5000000-0000-0000-0000-000000000007', 'a1000000-0000-0000-0000-000000000001', 'approved', 'Cron cleanup approved.', '2025-04-10 09:00:00+00'),
    ('f6000000-0000-0000-0000-000000000006', 'e5000000-0000-0000-0000-000000000008', 'a1000000-0000-0000-0000-000000000001', 'approved', 'Template update looks good.', '2025-03-15 10:00:00+00'),
    ('f6000000-0000-0000-0000-000000000007', 'e5000000-0000-0000-0000-000000000009', 'a1000000-0000-0000-0000-000000000001', 'approved', 'PCI remediation is critical — approved.', '2025-02-05 07:00:00+00'),
    ('f6000000-0000-0000-0000-000000000008', 'e5000000-0000-0000-0000-000000000010', 'a1000000-0000-0000-0000-000000000001', 'approved', 'Emergency approved — production impacting.', '2025-04-14 23:00:00+00')
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- COMMENTS (8): on CR-02, CR-03, CR-05, CR-07, CR-08, CR-09, CR-10
-- ============================================================
INSERT INTO comments (id, change_id, author_id, body, posted_at) VALUES
    ('17000000-0000-0000-0000-000000000001', 'e5000000-0000-0000-0000-000000000002', 'a1000000-0000-0000-0000-000000000003', 'Cert expiry date is May 1. We need this done by April 25 at the latest.', '2025-04-13 10:00:00+00'),
    ('17000000-0000-0000-0000-000000000002', 'e5000000-0000-0000-0000-000000000003', 'a1000000-0000-0000-0000-000000000001', 'Please coordinate with QA for staging smoke tests after deploy.', '2025-04-16 11:00:00+00'),
    ('17000000-0000-0000-0000-000000000003', 'e5000000-0000-0000-0000-000000000005', 'a1000000-0000-0000-0000-000000000004', 'Waiting for DBA sign-off on index naming convention.', '2025-03-06 08:00:00+00'),
    ('17000000-0000-0000-0000-000000000004', 'e5000000-0000-0000-0000-000000000005', 'a1000000-0000-0000-0000-000000000001', 'DBA approved. Proceed when ready.', '2025-03-07 09:00:00+00'),
    ('17000000-0000-0000-0000-000000000005', 'e5000000-0000-0000-0000-000000000007', 'a1000000-0000-0000-0000-000000000004', 'Cron manifest deployed to dev namespace. Monitoring for 24h.', '2025-04-17 10:00:00+00'),
    ('17000000-0000-0000-0000-000000000006', 'e5000000-0000-0000-0000-000000000008', 'a1000000-0000-0000-0000-000000000005', 'All templates verified against email clients. Looks good.', '2025-03-25 11:00:00+00'),
    ('17000000-0000-0000-0000-000000000007', 'e5000000-0000-0000-0000-000000000009', 'a1000000-0000-0000-0000-000000000004', 'TLS 1.0/1.1 disabled. PCI scan passed on re-run.', '2025-02-16 08:00:00+00'),
    ('17000000-0000-0000-0000-000000000008', 'e5000000-0000-0000-0000-000000000010', 'a1000000-0000-0000-0000-000000000005', 'Hotfix deployed. Monitoring token issuance rate.', '2025-04-15 01:00:00+00')
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- STATUS HISTORY: all non-draft changes (CR-02 through CR-10)
-- ============================================================
INSERT INTO status_history (id, change_id, from_status, to_status, actor_id, changed_at, reason) VALUES
    -- CR-02: draft→submitted
    ('aa000000-0000-0000-0000-000000000001', 'e5000000-0000-0000-0000-000000000002', 'draft', 'submitted', 'a1000000-0000-0000-0000-000000000003', '2025-04-13 09:00:00+00', NULL),

    -- CR-03: draft→submitted→approved
    ('aa000000-0000-0000-0000-000000000002', 'e5000000-0000-0000-0000-000000000003', 'draft', 'submitted', 'a1000000-0000-0000-0000-000000000002', '2025-04-15 10:00:00+00', NULL),
    ('aa000000-0000-0000-0000-000000000003', 'e5000000-0000-0000-0000-000000000003', 'submitted', 'approved', 'a1000000-0000-0000-0000-000000000001', '2025-04-16 10:00:00+00', NULL),

    -- CR-04: draft→submitted→rejected
    ('aa000000-0000-0000-0000-000000000004', 'e5000000-0000-0000-0000-000000000004', 'draft', 'submitted', 'a1000000-0000-0000-0000-000000000003', '2025-03-02 11:00:00+00', NULL),
    ('aa000000-0000-0000-0000-000000000005', 'e5000000-0000-0000-0000-000000000004', 'submitted', 'rejected', 'a1000000-0000-0000-0000-000000000001', '2025-03-05 11:00:00+00', 'Insufficient rollback plan.'),

    -- CR-05: draft→submitted→approved→scheduled
    ('aa000000-0000-0000-0000-000000000006', 'e5000000-0000-0000-0000-000000000005', 'draft', 'submitted', 'a1000000-0000-0000-0000-000000000002', '2025-02-21 08:00:00+00', NULL),
    ('aa000000-0000-0000-0000-000000000007', 'e5000000-0000-0000-0000-000000000005', 'submitted', 'approved', 'a1000000-0000-0000-0000-000000000001', '2025-03-01 08:00:00+00', NULL),
    ('aa000000-0000-0000-0000-000000000008', 'e5000000-0000-0000-0000-000000000005', 'approved', 'scheduled', 'a1000000-0000-0000-0000-000000000001', '2025-03-05 08:00:00+00', NULL),

    -- CR-06: draft→submitted→approved→scheduled
    ('aa000000-0000-0000-0000-000000000009', 'e5000000-0000-0000-0000-000000000006', 'draft', 'submitted', 'a1000000-0000-0000-0000-000000000003', '2025-02-26 12:00:00+00', NULL),
    ('aa000000-0000-0000-0000-000000000010', 'e5000000-0000-0000-0000-000000000006', 'submitted', 'approved', 'a1000000-0000-0000-0000-000000000001', '2025-03-05 12:00:00+00', NULL),
    ('aa000000-0000-0000-0000-000000000011', 'e5000000-0000-0000-0000-000000000006', 'approved', 'scheduled', 'a1000000-0000-0000-0000-000000000001', '2025-03-08 12:00:00+00', NULL),

    -- CR-07: draft→submitted→approved→scheduled→implementing
    ('aa000000-0000-0000-0000-000000000012', 'e5000000-0000-0000-0000-000000000007', 'draft', 'submitted', 'a1000000-0000-0000-0000-000000000002', '2025-04-02 09:00:00+00', NULL),
    ('aa000000-0000-0000-0000-000000000013', 'e5000000-0000-0000-0000-000000000007', 'submitted', 'approved', 'a1000000-0000-0000-0000-000000000001', '2025-04-10 09:00:00+00', NULL),
    ('aa000000-0000-0000-0000-000000000014', 'e5000000-0000-0000-0000-000000000007', 'approved', 'scheduled', 'a1000000-0000-0000-0000-000000000001', '2025-04-15 09:00:00+00', NULL),
    ('aa000000-0000-0000-0000-000000000015', 'e5000000-0000-0000-0000-000000000007', 'scheduled', 'implementing', 'a1000000-0000-0000-0000-000000000004', '2025-04-17 09:00:00+00', NULL),

    -- CR-08: draft→submitted→approved→scheduled→implementing→completed
    ('aa000000-0000-0000-0000-000000000016', 'e5000000-0000-0000-0000-000000000008', 'draft', 'submitted', 'a1000000-0000-0000-0000-000000000003', '2025-03-11 10:00:00+00', NULL),
    ('aa000000-0000-0000-0000-000000000017', 'e5000000-0000-0000-0000-000000000008', 'submitted', 'approved', 'a1000000-0000-0000-0000-000000000001', '2025-03-15 10:00:00+00', NULL),
    ('aa000000-0000-0000-0000-000000000018', 'e5000000-0000-0000-0000-000000000008', 'approved', 'scheduled', 'a1000000-0000-0000-0000-000000000001', '2025-03-20 10:00:00+00', NULL),
    ('aa000000-0000-0000-0000-000000000019', 'e5000000-0000-0000-0000-000000000008', 'scheduled', 'implementing', 'a1000000-0000-0000-0000-000000000005', '2025-03-24 10:00:00+00', NULL),
    ('aa000000-0000-0000-0000-000000000020', 'e5000000-0000-0000-0000-000000000008', 'implementing', 'completed', 'a1000000-0000-0000-0000-000000000005', '2025-03-26 10:00:00+00', NULL),

    -- CR-09: draft→submitted→approved→scheduled→implementing→completed→closed
    ('aa000000-0000-0000-0000-000000000021', 'e5000000-0000-0000-0000-000000000009', 'draft', 'submitted', 'a1000000-0000-0000-0000-000000000002', '2025-02-02 07:00:00+00', NULL),
    ('aa000000-0000-0000-0000-000000000022', 'e5000000-0000-0000-0000-000000000009', 'submitted', 'approved', 'a1000000-0000-0000-0000-000000000001', '2025-02-05 07:00:00+00', NULL),
    ('aa000000-0000-0000-0000-000000000023', 'e5000000-0000-0000-0000-000000000009', 'approved', 'scheduled', 'a1000000-0000-0000-0000-000000000001', '2025-02-10 07:00:00+00', NULL),
    ('aa000000-0000-0000-0000-000000000024', 'e5000000-0000-0000-0000-000000000009', 'scheduled', 'implementing', 'a1000000-0000-0000-0000-000000000004', '2025-02-14 07:00:00+00', NULL),
    ('aa000000-0000-0000-0000-000000000025', 'e5000000-0000-0000-0000-000000000009', 'implementing', 'completed', 'a1000000-0000-0000-0000-000000000004', '2025-02-16 07:00:00+00', NULL),
    ('aa000000-0000-0000-0000-000000000026', 'e5000000-0000-0000-0000-000000000009', 'completed', 'closed', 'a1000000-0000-0000-0000-000000000001', '2025-02-20 07:00:00+00', NULL),

    -- CR-10: draft→submitted→approved→implementing (emergency skip scheduled)
    ('aa000000-0000-0000-0000-000000000027', 'e5000000-0000-0000-0000-000000000010', 'draft', 'submitted', 'a1000000-0000-0000-0000-000000000002', '2025-04-14 22:05:00+00', NULL),
    ('aa000000-0000-0000-0000-000000000028', 'e5000000-0000-0000-0000-000000000010', 'submitted', 'approved', 'a1000000-0000-0000-0000-000000000001', '2025-04-14 23:00:00+00', 'Emergency — production auth broken.'),
    ('aa000000-0000-0000-0000-000000000029', 'e5000000-0000-0000-0000-000000000010', 'approved', 'implementing', 'a1000000-0000-0000-0000-000000000005', '2025-04-15 00:30:00+00', 'Emergency path: skipping scheduled.')
ON CONFLICT (id) DO NOTHING;
