-- 002_seed.sql
-- Dev/test fixture data for gitlab-pipeline-smoke (Team Notice Board API)
-- Idempotent: ON CONFLICT DO NOTHING; safe to run multiple times.
-- FR-11: 3 categories (General, HR, Engineering) + 5 notices with stable UUIDs.

SET search_path TO gitlab_pipeline_smoke;

-- ─── Categories (stable UUIDs) ────────────────────────────────────────────────
-- cat-1: General  | cat-2: HR  | cat-3: Engineering
INSERT INTO gitlab_pipeline_smoke.categories (id, name, description, created_at)
VALUES
    ('a1000000-0000-4000-8000-000000000001',
     'General',
     'Company-wide announcements and general team updates.',
     now() - INTERVAL '30 days'),

    ('a1000000-0000-4000-8000-000000000002',
     'HR',
     'Human Resources notices: benefits, policies, and events.',
     now() - INTERVAL '25 days'),

    ('a1000000-0000-4000-8000-000000000003',
     'Engineering',
     'Engineering team: deployments, on-call rotations, and RFC reviews.',
     now() - INTERVAL '20 days'),

    ('a1000000-0000-4000-8000-000000000004',
     'Operations',
     'Infrastructure, tooling, and operational announcements.',
     now() - INTERVAL '15 days'),

    ('a1000000-0000-4000-8000-000000000005',
     'Product',
     'Product roadmap updates, feature launches, and feedback requests.',
     now() - INTERVAL '10 days')
ON CONFLICT (name) DO NOTHING;

-- ─── Notices (stable UUIDs) ───────────────────────────────────────────────────
-- notice-1: ACTIVE          (General)       — is_archived=false, starts_at past, ends_at future
-- notice-2: FUTURE          (Engineering)   — is_archived=false, starts_at in future
-- notice-3: EXPIRED         (HR)            — is_archived=false, starts_at past, ends_at in past
-- notice-4: ARCHIVED        (General)       — is_archived=true
-- notice-5: ACTIVE          (Engineering)   — is_archived=false, starts_at past, ends_at=NULL
-- bonus rows to meet seedMinRows=5 (5 notices + 5 categories already satisfies requirement)

INSERT INTO gitlab_pipeline_smoke.notices
    (id, category_id, title, body, author_name, starts_at, ends_at, is_archived, created_at, updated_at)
VALUES
    -- 1. Active notice (General) — visible in active_only=true
    ('b1000000-0000-4000-8000-000000000001',
     'a1000000-0000-4000-8000-000000000001',
     'Welcome to the Team Notice Board',
     'This notice board is your central hub for team announcements. Bookmark `/docs` to explore the full API. Active notices appear here by default.',
     'Admin Team',
     now() - INTERVAL '5 days',
     now() + INTERVAL '30 days',
     false,
     now() - INTERVAL '5 days',
     now() - INTERVAL '5 days'),

    -- 2. Future notice (Engineering) — starts_at > now(), NOT in active_only=true
    ('b1000000-0000-4000-8000-000000000002',
     'a1000000-0000-4000-8000-000000000003',
     'Scheduled Maintenance Window — 2025-08-01',
     'The production database will undergo a planned maintenance window on 2025-08-01 from 02:00–04:00 UTC. Expect brief read-only interruptions.',
     'SRE Team',
     now() + INTERVAL '7 days',
     now() + INTERVAL '8 days',
     false,
     now() - INTERVAL '2 days',
     now() - INTERVAL '2 days'),

    -- 3. Expired notice (HR) — ends_at in past, NOT in active_only=true
    ('b1000000-0000-4000-8000-000000000003',
     'a1000000-0000-4000-8000-000000000002',
     'Open Enrollment Deadline — Action Required',
     'Please complete your benefits open enrollment selection by the deadline. Contact hr@example.com with any questions.',
     'HR Department',
     now() - INTERVAL '30 days',
     now() - INTERVAL '1 day',
     false,
     now() - INTERVAL '30 days',
     now() - INTERVAL '30 days'),

    -- 4. Archived notice (General) — is_archived=true, NOT in active_only=true
    ('b1000000-0000-4000-8000-000000000004',
     'a1000000-0000-4000-8000-000000000001',
     'Q1 All-Hands Meeting Summary',
     'Thank you to everyone who attended the Q1 all-hands. Recording available in the shared drive. Key decisions: roadmap approved, hiring targets set.',
     'Leadership Team',
     now() - INTERVAL '60 days',
     now() - INTERVAL '45 days',
     true,
     now() - INTERVAL '60 days',
     now() - INTERVAL '45 days'),

    -- 5. Active notice (Engineering) — no ends_at, visible in active_only=true
    ('b1000000-0000-4000-8000-000000000005',
     'a1000000-0000-4000-8000-000000000003',
     'On-Call Rotation Updated for July',
     'The on-call rotation for July has been updated. Please review the PagerDuty schedule and confirm your shifts by end of week.',
     'Engineering Manager',
     now() - INTERVAL '3 days',
     NULL,
     false,
     now() - INTERVAL '3 days',
     now() - INTERVAL '3 days'),

    -- 6. Active notice (Operations) — no ends_at, visible in active_only=true
    ('b1000000-0000-4000-8000-000000000006',
     'a1000000-0000-4000-8000-000000000004',
     'New VPN Policy Effective Immediately',
     'All remote access to internal systems must now use the updated VPN client (v3.2+). Please upgrade before Monday. Instructions in the IT wiki.',
     'IT Operations',
     now() - INTERVAL '1 day',
     NULL,
     false,
     now() - INTERVAL '1 day',
     now() - INTERVAL '1 day'),

    -- 7. Active notice (Product) — ends_at future, visible in active_only=true
    ('b1000000-0000-4000-8000-000000000007',
     'a1000000-0000-4000-8000-000000000005',
     'Beta Feature Feedback Requested',
     'We are collecting feedback on the new dashboard beta. Please test and submit your thoughts via the feedback form linked in Slack #product-beta. Closes end of month.',
     'Product Team',
     now() - INTERVAL '2 days',
     now() + INTERVAL '14 days',
     false,
     now() - INTERVAL '2 days',
     now() - INTERVAL '2 days'),

    -- 8. Archived notice (HR) — is_archived=true
    ('b1000000-0000-4000-8000-000000000008',
     'a1000000-0000-4000-8000-000000000002',
     'Holiday Schedule 2024',
     'The approved company holiday schedule for 2024 has been published. Please review and update your time-off plans accordingly.',
     'HR Department',
     now() - INTERVAL '120 days',
     now() - INTERVAL '30 days',
     true,
     now() - INTERVAL '120 days',
     now() - INTERVAL '90 days')

ON CONFLICT (id) DO NOTHING;
