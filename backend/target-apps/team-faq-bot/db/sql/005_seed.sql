-- 005_seed.sql
-- Dev/test seed data for team-faq-bot

-- ============================================================
-- faq_collection: 5 rows (one active for testing, rest inactive)
-- ============================================================
INSERT INTO faq_collection (id, filename, raw_text, char_count, uploaded_at, is_active)
VALUES
    (1, 'engineering-faq-v1.txt',
     'Q: How do I request PTO?
A: Submit a request in BambooHR at least 3 business days in advance.

Q: How do I get a new laptop?
A: File an IT ticket in ServiceNow under Hardware Provisioning.

Q: What is the deploy process?
A: Merge to main, CI runs tests, then auto-deploys to staging. Prod requires manual approval in ArgoCD.

Q: Where is the on-call schedule?
A: Check PagerDuty. Rotations are updated every Monday.

Q: How do I access the VPN?
A: Download GlobalProtect and use your SSO credentials. Config guide is on the wiki under Networking.',
     487, '2024-01-15 09:00:00+00', true),
    (2, 'engineering-faq-v0.txt',
     'Q: How do I request PTO?
A: Email your manager.

Q: Deploy process?
A: Ask the tech lead.',
     89, '2024-01-10 09:00:00+00', false),
    (3, 'onboarding-faq-draft.txt',
     'Q: When is orientation?
A: First Monday of your start month at 9 AM.

Q: Who is my buddy?
A: Check the onboarding Slack channel.',
     133, '2024-01-05 09:00:00+00', false),
    (4, 'ops-faq-old.txt',
     'Q: How do I escalate an incident?
A: Page the on-call via PagerDuty.

Q: Where are runbooks?
A: In the ops/ directory of the monorepo.',
     139, '2023-12-20 09:00:00+00', false),
    (5, 'placeholder-empty.txt',
     'No content yet.',
     15, '2023-12-01 09:00:00+00', false)
ON CONFLICT DO NOTHING;

-- Reset sequence to avoid PK conflicts on future inserts
SELECT setval('faq_collection_id_seq', (SELECT COALESCE(MAX(id), 0) FROM faq_collection));

-- ============================================================
-- faq_chunks: 6 rows linked to faq_collection id=1 (active)
-- Using zero vectors as dev placeholders (1024 dimensions)
-- ============================================================
INSERT INTO faq_chunks (id, collection_id, heading, chunk_text, embedding)
VALUES
    (1, 1, 'PTO Policy',
     'Q: How do I request PTO?
A: Submit a request in BambooHR at least 3 business days in advance.',
     (SELECT array_agg(0.0)::vector FROM generate_series(1,1024))),
    (2, 1, 'Laptop Provisioning',
     'Q: How do I get a new laptop?
A: File an IT ticket in ServiceNow under Hardware Provisioning.',
     (SELECT array_agg(0.0)::vector FROM generate_series(1,1024))),
    (3, 1, 'Deploy Process',
     'Q: What is the deploy process?
A: Merge to main, CI runs tests, then auto-deploys to staging. Prod requires manual approval in ArgoCD.',
     (SELECT array_agg(0.0)::vector FROM generate_series(1,1024))),
    (4, 1, 'On-Call Schedule',
     'Q: Where is the on-call schedule?
A: Check PagerDuty. Rotations are updated every Monday.',
     (SELECT array_agg(0.0)::vector FROM generate_series(1,1024))),
    (5, 1, 'VPN Access',
     'Q: How do I access the VPN?
A: Download GlobalProtect and use your SSO credentials. Config guide is on the wiki under Networking.',
     (SELECT array_agg(0.0)::vector FROM generate_series(1,1024))),
    (6, 1, NULL,
     'General: For any other questions, ask in the #engineering-help Slack channel.',
     (SELECT array_agg(0.0)::vector FROM generate_series(1,1024)))
ON CONFLICT DO NOTHING;

SELECT setval('faq_chunks_id_seq', (SELECT COALESCE(MAX(id), 0) FROM faq_chunks));

-- ============================================================
-- question_log: 8 rows — mix of answered and not_in_faq for gap-list testing
-- ============================================================
INSERT INTO question_log (id, question_text, status, logged_at, expires_at)
VALUES
    (1, 'How do I request PTO?', 'answered',
     '2024-02-01 10:15:00+00', '2024-05-01 10:15:00+00'),
    (2, 'What is the deploy process?', 'answered',
     '2024-02-02 11:30:00+00', '2024-05-02 11:30:00+00'),
    (3, 'How do I set up local dev environment?', 'not_in_faq',
     '2024-02-03 09:00:00+00', '2024-05-03 09:00:00+00'),
    (4, 'Where do I find the architecture diagrams?', 'not_in_faq',
     '2024-02-04 14:20:00+00', '2024-05-04 14:20:00+00'),
    (5, 'How do I get a new laptop?', 'answered',
     '2024-02-05 08:45:00+00', '2024-05-05 08:45:00+00'),
    (6, 'What is the code review policy?', 'not_in_faq',
     '2024-02-06 16:10:00+00', '2024-05-06 16:10:00+00'),
    (7, 'How do I access the staging database?', 'not_in_faq',
     '2024-02-07 13:00:00+00', '2024-05-07 13:00:00+00'),
    (8, 'Where is the on-call schedule?', 'answered',
     '2024-02-08 10:30:00+00', '2024-05-08 10:30:00+00')
ON CONFLICT DO NOTHING;

SELECT setval('question_log_id_seq', (SELECT COALESCE(MAX(id), 0) FROM question_log));
