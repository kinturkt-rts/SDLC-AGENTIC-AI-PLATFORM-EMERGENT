-- Password for all seed users: "KnowledgeHub2024!"
-- 011_seed.sql — Dev/test fixture data for support-knowledge-hub
SET search_path TO support_knowledge_hub, public;

-- ============================================================
-- USERS (6 rows: 2 employees, 2 contributors, 1 knowledge_admin, 1 leadership)
-- ============================================================
INSERT INTO users (id, email, display_name, role, hashed_password, created_at) VALUES
    ('a1000000-0000-0000-0000-000000000001', 'alice.chen@example.com',   'Alice Chen',     'employee',        '__BCRYPT_PLACEHOLDER__', '2024-01-10 08:00:00+00'),
    ('a1000000-0000-0000-0000-000000000002', 'bob.martinez@example.com', 'Bob Martinez',   'employee',        '__BCRYPT_PLACEHOLDER__', '2024-01-11 09:00:00+00'),
    ('a1000000-0000-0000-0000-000000000003', 'carol.jones@example.com',  'Carol Jones',    'contributor',     '__BCRYPT_PLACEHOLDER__', '2024-01-05 10:00:00+00'),
    ('a1000000-0000-0000-0000-000000000004', 'dave.lee@example.com',     'Dave Lee',       'contributor',     '__BCRYPT_PLACEHOLDER__', '2024-01-06 11:00:00+00'),
    ('a1000000-0000-0000-0000-000000000005', 'priya.patel@example.com',  'Priya Patel',    'knowledge_admin', '__BCRYPT_PLACEHOLDER__', '2024-01-01 07:00:00+00'),
    ('a1000000-0000-0000-0000-000000000006', 'frank.wu@example.com',     'Frank Wu',       'leadership',      '__BCRYPT_PLACEHOLDER__', '2024-01-02 08:00:00+00')
ON CONFLICT DO NOTHING;

-- ============================================================
-- CATEGORIES (5 rows)
-- ============================================================
INSERT INTO categories (id, name, is_active, created_at, created_by) VALUES
    ('b2000000-0000-0000-0000-000000000001', 'IT',         true, '2024-01-02 09:00:00+00', 'a1000000-0000-0000-0000-000000000005'),
    ('b2000000-0000-0000-0000-000000000002', 'HR',         true, '2024-01-02 09:05:00+00', 'a1000000-0000-0000-0000-000000000005'),
    ('b2000000-0000-0000-0000-000000000003', 'Finance',    true, '2024-01-02 09:10:00+00', 'a1000000-0000-0000-0000-000000000005'),
    ('b2000000-0000-0000-0000-000000000004', 'Legal',      true, '2024-01-02 09:15:00+00', 'a1000000-0000-0000-0000-000000000005'),
    ('b2000000-0000-0000-0000-000000000005', 'Onboarding', true, '2024-01-02 09:20:00+00', 'a1000000-0000-0000-0000-000000000005')
ON CONFLICT DO NOTHING;

-- ============================================================
-- ARTICLES (10 rows: 7 published, 2 draft, 1 archived)
-- Includes 2 semantically similar VPN articles (c30...01 and c30...02)
-- ============================================================
INSERT INTO articles (id, title, body, category_id, tags, author_id, state, created_at, updated_at, published_at, archived_at) VALUES
    ('c3000000-0000-0000-0000-000000000001', 'How to Reset Your VPN Connection',
     'If your VPN connection drops or fails to connect, follow these steps: 1. Disconnect the current session. 2. Clear cached credentials from your VPN client. 3. Restart the VPN client application. 4. Re-enter your corporate credentials. 5. If the issue persists, reboot your machine and retry.',
     'b2000000-0000-0000-0000-000000000001', ARRAY['vpn','network','troubleshooting'], 'a1000000-0000-0000-0000-000000000003',
     'published', '2024-01-15 10:00:00+00', '2024-01-15 10:00:00+00', '2024-01-15 10:00:00+00', NULL),

    ('c3000000-0000-0000-0000-000000000002', 'VPN Setup and Reconnection Guide',
     'This guide covers setting up and reconnecting your corporate VPN. To reconnect: open System Preferences > Network > VPN profile, click Disconnect, wait 10 seconds, then click Connect. If authentication fails, reset your AD password first and try again. Contact IT if problems continue.',
     'b2000000-0000-0000-0000-000000000001', ARRAY['vpn','setup','reconnect'], 'a1000000-0000-0000-0000-000000000004',
     'published', '2024-01-16 11:00:00+00', '2024-01-16 11:00:00+00', '2024-01-16 11:00:00+00', NULL),

    ('c3000000-0000-0000-0000-000000000003', 'Expense Report Submission Process',
     'To submit an expense report: 1. Log into the finance portal. 2. Click New Expense Report. 3. Attach receipts for each line item. 4. Select the correct cost center. 5. Submit for manager approval. Reports over $500 require VP sign-off.',
     'b2000000-0000-0000-0000-000000000003', ARRAY['expenses','finance','reimbursement'], 'a1000000-0000-0000-0000-000000000003',
     'published', '2024-01-17 09:00:00+00', '2024-01-17 09:00:00+00', '2024-01-17 09:00:00+00', NULL),

    ('c3000000-0000-0000-0000-000000000004', 'New Hire Onboarding Checklist',
     'Welcome to the team! Your first week checklist: Day 1 - Badge pickup, laptop setup, meet your buddy. Day 2 - HR orientation, benefits enrollment. Day 3 - Team intro, access provisioning. Day 4 - Tool training. Day 5 - First 1:1 with manager.',
     'b2000000-0000-0000-0000-000000000005', ARRAY['onboarding','new-hire','checklist'], 'a1000000-0000-0000-0000-000000000004',
     'published', '2024-01-18 08:00:00+00', '2024-01-18 08:00:00+00', '2024-01-18 08:00:00+00', NULL),

    ('c3000000-0000-0000-0000-000000000005', 'Requesting Time Off in the HR System',
     'To request PTO: Navigate to HR Portal > Time Off > New Request. Select dates, choose PTO type (vacation, sick, personal). Add a note for your manager. Submit. Approval typically takes 1-2 business days. Check your balance on the dashboard.',
     'b2000000-0000-0000-0000-000000000002', ARRAY['pto','time-off','hr'], 'a1000000-0000-0000-0000-000000000003',
     'published', '2024-01-19 14:00:00+00', '2024-01-19 14:00:00+00', '2024-01-19 14:00:00+00', NULL),

    ('c3000000-0000-0000-0000-000000000006', 'Wi-Fi Troubleshooting for Office Networks',
     'If you cannot connect to the office Wi-Fi: 1. Forget the network and reconnect. 2. Ensure you are using CorpNet-5G (not guest). 3. Check your certificate is current. 4. Restart your network adapter. 5. Visit IT help desk if unresolved.',
     'b2000000-0000-0000-0000-000000000001', ARRAY['wifi','network','office'], 'a1000000-0000-0000-0000-000000000004',
     'published', '2024-01-20 10:30:00+00', '2024-01-20 10:30:00+00', '2024-01-20 10:30:00+00', NULL),

    ('c3000000-0000-0000-0000-000000000007', 'Understanding Company NDA Requirements',
     'All employees must sign the standard NDA before accessing proprietary materials. The NDA covers trade secrets, client lists, and internal strategy documents. Contact Legal for exceptions or questions about scope.',
     'b2000000-0000-0000-0000-000000000004', ARRAY['nda','legal','compliance'], 'a1000000-0000-0000-0000-000000000003',
     'published', '2024-01-21 09:00:00+00', '2024-01-21 09:00:00+00', '2024-01-21 09:00:00+00', NULL),

    ('c3000000-0000-0000-0000-000000000008', 'Draft: Multi-Factor Authentication Setup',
     'This draft covers how to set up MFA on your corporate accounts. Steps TBD pending security team review.',
     'b2000000-0000-0000-0000-000000000001', ARRAY['mfa','security'], 'a1000000-0000-0000-0000-000000000003',
     'draft', '2024-02-01 08:00:00+00', '2024-02-01 08:00:00+00', NULL, NULL),

    ('c3000000-0000-0000-0000-000000000009', 'Draft: Remote Work Equipment Policy',
     'Outlines the equipment allowance and return policy for remote workers. Under review.',
     'b2000000-0000-0000-0000-000000000002', ARRAY['remote','equipment','policy'], 'a1000000-0000-0000-0000-000000000004',
     'draft', '2024-02-02 09:00:00+00', '2024-02-02 09:00:00+00', NULL, NULL),

    ('c3000000-0000-0000-0000-000000000010', 'Deprecated: Old Badge Access Procedure',
     'This article described the previous badge access system which has been replaced.',
     'b2000000-0000-0000-0000-000000000001', ARRAY['badge','access','deprecated'], 'a1000000-0000-0000-0000-000000000003',
     'archived', '2024-01-05 08:00:00+00', '2024-02-10 08:00:00+00', '2024-01-05 08:00:00+00', '2024-02-10 08:00:00+00')
ON CONFLICT DO NOTHING;

-- ============================================================
-- ARTICLE_CHUNKS (5 rows — representative; real embeddings generated at runtime)
-- Using zero vectors as placeholders; app re-embeds on publish
-- ============================================================
INSERT INTO article_chunks (id, article_id, chunk_index, chunk_text, embedding) VALUES
    ('d4000000-0000-0000-0000-000000000001', 'c3000000-0000-0000-0000-000000000001', 0,
     'If your VPN connection drops or fails to connect, follow these steps: 1. Disconnect the current session. 2. Clear cached credentials from your VPN client.',
     (SELECT array_fill(0.0, ARRAY[1024])::vector)),
    ('d4000000-0000-0000-0000-000000000002', 'c3000000-0000-0000-0000-000000000001', 1,
     '3. Restart the VPN client application. 4. Re-enter your corporate credentials. 5. If the issue persists, reboot your machine and retry.',
     (SELECT array_fill(0.0, ARRAY[1024])::vector)),
    ('d4000000-0000-0000-0000-000000000003', 'c3000000-0000-0000-0000-000000000002', 0,
     'This guide covers setting up and reconnecting your corporate VPN. To reconnect: open System Preferences > Network > VPN profile, click Disconnect, wait 10 seconds, then click Connect.',
     (SELECT array_fill(0.0, ARRAY[1024])::vector)),
    ('d4000000-0000-0000-0000-000000000004', 'c3000000-0000-0000-0000-000000000003', 0,
     'To submit an expense report: 1. Log into the finance portal. 2. Click New Expense Report. 3. Attach receipts for each line item.',
     (SELECT array_fill(0.0, ARRAY[1024])::vector)),
    ('d4000000-0000-0000-0000-000000000005', 'c3000000-0000-0000-0000-000000000004', 0,
     'Welcome to the team! Your first week checklist: Day 1 - Badge pickup, laptop setup, meet your buddy. Day 2 - HR orientation, benefits enrollment.',
     (SELECT array_fill(0.0, ARRAY[1024])::vector))
ON CONFLICT DO NOTHING;

-- ============================================================
-- SEARCH_LOGS (10 rows)
-- ============================================================
INSERT INTO search_logs (id, user_id_hash, query_text, category_filter, result_count, executed_at) VALUES
    ('e5000000-0000-0000-0000-000000000001', 'sha256_alice_hash_001', 'how to reset VPN', 'b2000000-0000-0000-0000-000000000001', 2, '2024-02-01 10:00:00+00'),
    ('e5000000-0000-0000-0000-000000000002', 'sha256_bob_hash_001',   'expense report submission', NULL, 1, '2024-02-01 11:00:00+00'),
    ('e5000000-0000-0000-0000-000000000003', 'sha256_alice_hash_001', 'onboarding checklist new hire', NULL, 1, '2024-02-02 09:00:00+00'),
    ('e5000000-0000-0000-0000-000000000004', 'sha256_bob_hash_001',   'contractor onboarding process', NULL, 0, '2024-02-02 10:00:00+00'),
    ('e5000000-0000-0000-0000-000000000005', 'sha256_alice_hash_001', 'contractor onboarding process', NULL, 0, '2024-02-03 08:00:00+00'),
    ('e5000000-0000-0000-0000-000000000006', 'sha256_bob_hash_001',   'contractor onboarding process', NULL, 0, '2024-02-04 09:00:00+00'),
    ('e5000000-0000-0000-0000-000000000007', 'sha256_alice_hash_001', 'wifi not working office', 'b2000000-0000-0000-0000-000000000001', 1, '2024-02-05 14:00:00+00'),
    ('e5000000-0000-0000-0000-000000000008', 'sha256_bob_hash_001',   'NDA scope questions', 'b2000000-0000-0000-0000-000000000004', 1, '2024-02-06 10:00:00+00'),
    ('e5000000-0000-0000-0000-000000000009', 'sha256_alice_hash_001', 'time off request how', NULL, 1, '2024-02-07 15:00:00+00'),
    ('e5000000-0000-0000-0000-000000000010', 'sha256_bob_hash_001',   'parking pass renewal', NULL, 0, '2024-02-08 11:00:00+00')
ON CONFLICT DO NOTHING;

-- ============================================================
-- SEARCH_RESULT_ITEMS (8 rows)
-- ============================================================
INSERT INTO search_result_items (id, search_log_id, article_id, rank_position) VALUES
    ('f6000000-0000-0000-0000-000000000001', 'e5000000-0000-0000-0000-000000000001', 'c3000000-0000-0000-0000-000000000001', 1),
    ('f6000000-0000-0000-0000-000000000002', 'e5000000-0000-0000-0000-000000000001', 'c3000000-0000-0000-0000-000000000002', 2),
    ('f6000000-0000-0000-0000-000000000003', 'e5000000-0000-0000-0000-000000000002', 'c3000000-0000-0000-0000-000000000003', 1),
    ('f6000000-0000-0000-0000-000000000004', 'e5000000-0000-0000-0000-000000000003', 'c3000000-0000-0000-0000-000000000004', 1),
    ('f6000000-0000-0000-0000-000000000005', 'e5000000-0000-0000-0000-000000000007', 'c3000000-0000-0000-0000-000000000006', 1),
    ('f6000000-0000-0000-0000-000000000006', 'e5000000-0000-0000-0000-000000000008', 'c3000000-0000-0000-0000-000000000007', 1),
    ('f6000000-0000-0000-0000-000000000007', 'e5000000-0000-0000-0000-000000000009', 'c3000000-0000-0000-0000-000000000005', 1),
    ('f6000000-0000-0000-0000-000000000008', 'e5000000-0000-0000-0000-000000000004', 'c3000000-0000-0000-0000-000000000004', 1)
ON CONFLICT DO NOTHING;

-- ============================================================
-- FEEDBACK (7 rows — mix of helpful and not_helpful to populate gap report)
-- ============================================================
INSERT INTO feedback (id, search_log_id, article_id, user_id_hash, signal, created_at) VALUES
    ('17000000-0000-0000-0000-000000000001', 'e5000000-0000-0000-0000-000000000001', 'c3000000-0000-0000-0000-000000000001', 'sha256_alice_hash_001', 'helpful',     '2024-02-01 10:05:00+00'),
    ('17000000-0000-0000-0000-000000000002', 'e5000000-0000-0000-0000-000000000001', 'c3000000-0000-0000-0000-000000000002', 'sha256_alice_hash_001', 'helpful',     '2024-02-01 10:06:00+00'),
    ('17000000-0000-0000-0000-000000000003', 'e5000000-0000-0000-0000-000000000002', 'c3000000-0000-0000-0000-000000000003', 'sha256_bob_hash_001',   'helpful',     '2024-02-01 11:05:00+00'),
    ('17000000-0000-0000-0000-000000000004', 'e5000000-0000-0000-0000-000000000003', 'c3000000-0000-0000-0000-000000000004', 'sha256_alice_hash_001', 'helpful',     '2024-02-02 09:10:00+00'),
    ('17000000-0000-0000-0000-000000000005', 'e5000000-0000-0000-0000-000000000004', 'c3000000-0000-0000-0000-000000000004', 'sha256_bob_hash_001',   'not_helpful', '2024-02-02 10:10:00+00'),
    ('17000000-0000-0000-0000-000000000006', 'e5000000-0000-0000-0000-000000000007', 'c3000000-0000-0000-0000-000000000006', 'sha256_alice_hash_001', 'helpful',     '2024-02-05 14:05:00+00'),
    ('17000000-0000-0000-0000-000000000007', 'e5000000-0000-0000-0000-000000000009', 'c3000000-0000-0000-0000-000000000005', 'sha256_alice_hash_001', 'helpful',     '2024-02-07 15:05:00+00')
ON CONFLICT DO NOTHING;

-- ============================================================
-- PINNED_ARTICLES (3 rows in IT category)
-- ============================================================
INSERT INTO pinned_articles (id, category_id, article_id, pinned_by, pinned_at, display_order) VALUES
    ('18000000-0000-0000-0000-000000000001', 'b2000000-0000-0000-0000-000000000001', 'c3000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000005', '2024-02-01 12:00:00+00', 1),
    ('18000000-0000-0000-0000-000000000002', 'b2000000-0000-0000-0000-000000000001', 'c3000000-0000-0000-0000-000000000002', 'a1000000-0000-0000-0000-000000000005', '2024-02-01 12:05:00+00', 2),
    ('18000000-0000-0000-0000-000000000003', 'b2000000-0000-0000-0000-000000000001', 'c3000000-0000-0000-0000-000000000006', 'a1000000-0000-0000-0000-000000000005', '2024-02-01 12:10:00+00', 3)
ON CONFLICT DO NOTHING;
