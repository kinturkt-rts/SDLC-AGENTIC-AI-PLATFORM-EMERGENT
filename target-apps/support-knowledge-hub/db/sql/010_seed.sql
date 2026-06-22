-- Password for all seed users: "KnowledgeHub2024!"
-- 010_seed.sql — Dev/test fixture data for support-knowledge-hub
SET search_path TO support_knowledge_hub, public;

-- ============================================================
-- USERS (9 rows: 5 employee, 2 contributor, 1 knowledge_admin, 1 leadership)
-- ============================================================
INSERT INTO users (id, email, display_name, role, hashed_password, created_at) VALUES
    ('a1000000-0000-0000-0000-000000000001', 'priya@example.com',    'Priya Sharma',     'knowledge_admin', '__BCRYPT_PLACEHOLDER__', '2024-01-05 09:00:00+00'),
    ('a1000000-0000-0000-0000-000000000002', 'carlos@example.com',   'Carlos Rivera',    'contributor',     '__BCRYPT_PLACEHOLDER__', '2024-01-06 10:00:00+00'),
    ('a1000000-0000-0000-0000-000000000003', 'mei@example.com',      'Mei Chen',         'contributor',     '__BCRYPT_PLACEHOLDER__', '2024-01-07 11:00:00+00'),
    ('a1000000-0000-0000-0000-000000000004', 'james@example.com',    'James Wilson',     'leadership',      '__BCRYPT_PLACEHOLDER__', '2024-01-08 08:00:00+00'),
    ('a1000000-0000-0000-0000-000000000005', 'alice@example.com',    'Alice Johnson',    'employee',        '__BCRYPT_PLACEHOLDER__', '2024-01-10 09:30:00+00'),
    ('a1000000-0000-0000-0000-000000000006', 'bob@example.com',      'Bob Martinez',     'employee',        '__BCRYPT_PLACEHOLDER__', '2024-01-10 09:45:00+00'),
    ('a1000000-0000-0000-0000-000000000007', 'dana@example.com',     'Dana Park',        'employee',        '__BCRYPT_PLACEHOLDER__', '2024-01-11 10:00:00+00'),
    ('a1000000-0000-0000-0000-000000000008', 'frank@example.com',    'Frank Okafor',     'employee',        '__BCRYPT_PLACEHOLDER__', '2024-01-12 08:30:00+00'),
    ('a1000000-0000-0000-0000-000000000009', 'grace@example.com',    'Grace Liu',        'employee',        '__BCRYPT_PLACEHOLDER__', '2024-01-13 14:00:00+00')
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- CATEGORIES (5 rows)
-- ============================================================
INSERT INTO categories (id, name, slug, created_by, created_at) VALUES
    ('b2000000-0000-0000-0000-000000000001', 'IT',         'it',         'a1000000-0000-0000-0000-000000000001', '2024-01-15 09:00:00+00'),
    ('b2000000-0000-0000-0000-000000000002', 'HR',         'hr',         'a1000000-0000-0000-0000-000000000001', '2024-01-15 09:05:00+00'),
    ('b2000000-0000-0000-0000-000000000003', 'Finance',    'finance',    'a1000000-0000-0000-0000-000000000001', '2024-01-15 09:10:00+00'),
    ('b2000000-0000-0000-0000-000000000004', 'Legal',      'legal',      'a1000000-0000-0000-0000-000000000001', '2024-01-15 09:15:00+00'),
    ('b2000000-0000-0000-0000-000000000005', 'Facilities', 'facilities', 'a1000000-0000-0000-0000-000000000001', '2024-01-15 09:20:00+00')
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- ARTICLES (10 rows: 7 published, 2 draft, 1 archived)
-- Includes 2 near-duplicate pairs for similarity demo
-- ============================================================
INSERT INTO articles (id, title, body, category_id, tags, author_id, status, created_at, updated_at, published_at, archived_at) VALUES
    ('c3000000-0000-0000-0000-000000000001',
     'How to Connect to the Corporate VPN',
     'This guide covers connecting to the corporate VPN from home or public networks. Step 1: Download the GlobalProtect client from the IT portal. Step 2: Enter the gateway address vpn.company.com. Step 3: Authenticate with your company credentials and MFA token. Step 4: Verify connection status shows green.',
     'b2000000-0000-0000-0000-000000000001', ARRAY['vpn','remote-access','networking'],
     'a1000000-0000-0000-0000-000000000002', 'published',
     '2024-01-20 10:00:00+00', '2024-01-20 10:00:00+00', '2024-01-20 10:00:00+00', NULL),

    ('c3000000-0000-0000-0000-000000000002',
     'VPN Setup Guide for Remote Workers',
     'Setting up VPN access for remote work is simple. First, install GlobalProtect from the company IT portal. Next, configure the gateway to vpn.company.com. Then log in using your corporate email and multi-factor authentication. Finally, confirm the connection indicator turns green.',
     'b2000000-0000-0000-0000-000000000001', ARRAY['vpn','setup','remote-work'],
     'a1000000-0000-0000-0000-000000000003', 'published',
     '2024-01-22 14:00:00+00', '2024-01-22 14:00:00+00', '2024-01-22 14:00:00+00', NULL),

    ('c3000000-0000-0000-0000-000000000003',
     'Password Reset Procedure',
     'If you have forgotten your corporate password, follow these steps: 1. Navigate to https://password.company.com. 2. Click Forgot Password. 3. Enter your employee email address. 4. Complete the identity verification via SMS or authenticator app. 5. Set a new password (minimum 12 characters, one uppercase, one number, one symbol). 6. Log in to all devices with the new password within 24 hours.',
     'b2000000-0000-0000-0000-000000000001', ARRAY['password','security','account'],
     'a1000000-0000-0000-0000-000000000002', 'published',
     '2024-01-25 09:00:00+00', '2024-01-25 09:00:00+00', '2024-01-25 09:00:00+00', NULL),

    ('c3000000-0000-0000-0000-000000000004',
     'Expense Policy for Client Meals',
     'When expensing client meals, the following policy applies: Maximum per-person spend is $75 for lunch and $125 for dinner. Pre-approval is required for groups larger than 6. Receipts must be uploaded within 5 business days. Include attendee names and business purpose in the expense report. Alcohol is capped at 20% of the total bill.',
     'b2000000-0000-0000-0000-000000000002', ARRAY['expenses','policy','meals'],
     'a1000000-0000-0000-0000-000000000003', 'published',
     '2024-02-01 11:00:00+00', '2024-02-01 11:00:00+00', '2024-02-01 11:00:00+00', NULL),

    ('c3000000-0000-0000-0000-000000000005',
     'Client Entertainment Expense Guidelines',
     'Guidelines for client entertainment expenses: Lunch meetings have a limit of $75 per attendee, dinner meetings $125 per attendee. Groups over 6 require manager pre-approval. Submit receipts within 5 working days with attendee list and business justification. Alcoholic beverages must not exceed 20% of the receipt total.',
     'b2000000-0000-0000-0000-000000000002', ARRAY['expenses','entertainment','clients'],
     'a1000000-0000-0000-0000-000000000002', 'published',
     '2024-02-05 13:00:00+00', '2024-02-05 13:00:00+00', '2024-02-05 13:00:00+00', NULL),

    ('c3000000-0000-0000-0000-000000000006',
     'Quarterly Budget Submission Process',
     'Department heads must submit quarterly budgets by the 15th of the month preceding the quarter. Use the budget template in SharePoint under Finance > Templates. Include headcount projections, software licenses, and travel estimates. Finance reviews submissions within 5 business days and schedules a 30-minute alignment call if variances exceed 10%.',
     'b2000000-0000-0000-0000-000000000003', ARRAY['budget','quarterly','process'],
     'a1000000-0000-0000-0000-000000000003', 'published',
     '2024-02-10 10:00:00+00', '2024-02-10 10:00:00+00', '2024-02-10 10:00:00+00', NULL),

    ('c3000000-0000-0000-0000-000000000007',
     'Conference Room Booking Guidelines',
     'To book a conference room: 1. Open the Room Finder in Outlook or the Facilities portal. 2. Select floor and capacity. 3. Choose an available slot (max 2 hours for standard rooms, 4 hours for boardroom). 4. Add attendees. 5. Cancel unused bookings at least 1 hour before the slot. Repeat offenders who no-show 3 times in a month lose priority booking.',
     'b2000000-0000-0000-0000-000000000005', ARRAY['rooms','booking','facilities'],
     'a1000000-0000-0000-0000-000000000002', 'published',
     '2024-02-12 09:00:00+00', '2024-02-12 09:00:00+00', '2024-02-12 09:00:00+00', NULL),

    ('c3000000-0000-0000-0000-000000000008',
     'Setting Up Development Environment',
     'Draft guide for new engineers setting up their local development environment including IDE, Docker, and database tools. Covers VS Code extensions, Docker Desktop installation, and pgAdmin configuration.',
     'b2000000-0000-0000-0000-000000000001', ARRAY['dev','onboarding','tools'],
     'a1000000-0000-0000-0000-000000000002', 'draft',
     '2024-02-15 16:00:00+00', '2024-02-15 16:00:00+00', NULL, NULL),

    ('c3000000-0000-0000-0000-000000000009',
     'Parental Leave Policy Summary',
     'Draft summary of the updated parental leave policy covering eligibility, duration, and return-to-work support programs. Eligible after 12 months of service.',
     'b2000000-0000-0000-0000-000000000002', ARRAY['leave','parental','policy'],
     'a1000000-0000-0000-0000-000000000003', 'draft',
     '2024-02-18 11:00:00+00', '2024-02-18 11:00:00+00', NULL, NULL),

    ('c3000000-0000-0000-0000-000000000010',
     'Legacy Printer Setup (Deprecated)',
     'Instructions for connecting to the old HP LaserJet printers on Floor 2. These printers have been decommissioned as of March 2024.',
     'b2000000-0000-0000-0000-000000000001', ARRAY['printer','legacy','deprecated'],
     'a1000000-0000-0000-0000-000000000002', 'archived',
     '2024-01-10 08:00:00+00', '2024-03-01 09:00:00+00', '2024-01-10 08:00:00+00', '2024-03-01 09:00:00+00')
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- ARTICLE EMBEDDINGS (5 rows — placeholder zero-vectors; real embeddings generated at runtime)
-- Using repeat('0,', 383) || '0' to build a 384-dim zero vector string
-- ============================================================
INSERT INTO article_embeddings (id, article_id, chunk_index, chunk_text, embedding, model_version, embedded_at) VALUES
    ('ae000000-0000-0000-0000-000000000001', 'c3000000-0000-0000-0000-000000000001', 0,
     'This guide covers connecting to the corporate VPN from home or public networks.',
     ('[' || repeat('0,', 383) || '0]')::vector(384),
     'all-MiniLM-L6-v2', '2024-01-20 10:01:00+00'),
    ('ae000000-0000-0000-0000-000000000002', 'c3000000-0000-0000-0000-000000000002', 0,
     'Setting up VPN access for remote work is simple.',
     ('[' || repeat('0,', 383) || '0]')::vector(384),
     'all-MiniLM-L6-v2', '2024-01-22 14:01:00+00'),
    ('ae000000-0000-0000-0000-000000000003', 'c3000000-0000-0000-0000-000000000003', 0,
     'If you have forgotten your corporate password, follow these steps.',
     ('[' || repeat('0,', 383) || '0]')::vector(384),
     'all-MiniLM-L6-v2', '2024-01-25 09:01:00+00'),
    ('ae000000-0000-0000-0000-000000000004', 'c3000000-0000-0000-0000-000000000004', 0,
     'When expensing client meals, the following policy applies.',
     ('[' || repeat('0,', 383) || '0]')::vector(384),
     'all-MiniLM-L6-v2', '2024-02-01 11:01:00+00'),
    ('ae000000-0000-0000-0000-000000000005', 'c3000000-0000-0000-0000-000000000005', 0,
     'Guidelines for client entertainment expenses.',
     ('[' || repeat('0,', 383) || '0]')::vector(384),
     'all-MiniLM-L6-v2', '2024-02-05 13:01:00+00')
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- PINNED ARTICLES (5 rows: 3 IT, 1 HR, 1 Facilities)
-- ============================================================
INSERT INTO pinned_articles (id, category_id, article_id, pinned_by, pinned_at) VALUES
    ('d4000000-0000-0000-0000-000000000001', 'b2000000-0000-0000-0000-000000000001', 'c3000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000001', '2024-01-21 09:00:00+00'),
    ('d4000000-0000-0000-0000-000000000002', 'b2000000-0000-0000-0000-000000000001', 'c3000000-0000-0000-0000-000000000003', 'a1000000-0000-0000-0000-000000000001', '2024-01-26 10:00:00+00'),
    ('d4000000-0000-0000-0000-000000000003', 'b2000000-0000-0000-0000-000000000001', 'c3000000-0000-0000-0000-000000000002', 'a1000000-0000-0000-0000-000000000001', '2024-01-23 11:00:00+00'),
    ('d4000000-0000-0000-0000-000000000004', 'b2000000-0000-0000-0000-000000000002', 'c3000000-0000-0000-0000-000000000004', 'a1000000-0000-0000-0000-000000000001', '2024-02-02 10:00:00+00'),
    ('d4000000-0000-0000-0000-000000000005', 'b2000000-0000-0000-0000-000000000005', 'c3000000-0000-0000-0000-000000000007', 'a1000000-0000-0000-0000-000000000001', '2024-02-13 09:00:00+00')
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- SEARCH EVENTS (10 rows — mix of good results, zero results, weak results for gaps demo)
-- ============================================================
INSERT INTO search_events (id, query_text, query_embedding, result_article_ids, result_count, role, timestamp) VALUES
    ('e5000000-0000-0000-0000-000000000001', 'how to connect to VPN from home', NULL,
     ARRAY['c3000000-0000-0000-0000-000000000001','c3000000-0000-0000-0000-000000000002']::uuid[], 2, 'employee', '2024-02-20 10:15:00+00'),
    ('e5000000-0000-0000-0000-000000000002', 'reset my password', NULL,
     ARRAY['c3000000-0000-0000-0000-000000000003']::uuid[], 1, 'employee', '2024-02-20 11:00:00+00'),
    ('e5000000-0000-0000-0000-000000000003', 'expense policy client dinner', NULL,
     ARRAY['c3000000-0000-0000-0000-000000000004','c3000000-0000-0000-0000-000000000005']::uuid[], 2, 'employee', '2024-02-21 09:30:00+00'),
    ('e5000000-0000-0000-0000-000000000004', 'how to order new monitor', NULL,
     ARRAY[]::uuid[], 0, 'employee', '2024-02-21 14:00:00+00'),
    ('e5000000-0000-0000-0000-000000000005', 'parking pass application', NULL,
     ARRAY[]::uuid[], 0, 'employee', '2024-02-22 08:45:00+00'),
    ('e5000000-0000-0000-0000-000000000006', 'book a conference room', NULL,
     ARRAY['c3000000-0000-0000-0000-000000000007']::uuid[], 1, 'employee', '2024-02-22 10:00:00+00'),
    ('e5000000-0000-0000-0000-000000000007', 'maternity leave policy', NULL,
     ARRAY[]::uuid[], 0, 'employee', '2024-02-23 09:15:00+00'),
    ('e5000000-0000-0000-0000-000000000008', 'quarterly budget deadline', NULL,
     ARRAY['c3000000-0000-0000-0000-000000000006']::uuid[], 1, 'contributor', '2024-02-23 11:30:00+00'),
    ('e5000000-0000-0000-0000-000000000009', 'wifi guest network setup', NULL,
     ARRAY[]::uuid[], 0, 'employee', '2024-02-24 13:00:00+00'),
    ('e5000000-0000-0000-0000-000000000010', 'travel reimbursement process', NULL,
     ARRAY[]::uuid[], 0, 'employee', '2024-02-25 16:00:00+00')
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- FEEDBACK (10 rows — unique (search_event_id, article_id) pairs)
-- ============================================================
INSERT INTO feedback (id, search_event_id, article_id, rating, timestamp) VALUES
    ('f6000000-0000-0000-0000-000000000001', 'e5000000-0000-0000-0000-000000000001', 'c3000000-0000-0000-0000-000000000001', 'helpful',     '2024-02-20 10:20:00+00'),
    ('f6000000-0000-0000-0000-000000000002', 'e5000000-0000-0000-0000-000000000001', 'c3000000-0000-0000-0000-000000000002', 'not_helpful', '2024-02-20 10:22:00+00'),
    ('f6000000-0000-0000-0000-000000000003', 'e5000000-0000-0000-0000-000000000002', 'c3000000-0000-0000-0000-000000000003', 'helpful',     '2024-02-20 11:05:00+00'),
    ('f6000000-0000-0000-0000-000000000004', 'e5000000-0000-0000-0000-000000000003', 'c3000000-0000-0000-0000-000000000004', 'helpful',     '2024-02-21 09:35:00+00'),
    ('f6000000-0000-0000-0000-000000000005', 'e5000000-0000-0000-0000-000000000003', 'c3000000-0000-0000-0000-000000000005', 'not_helpful', '2024-02-21 09:40:00+00'),
    ('f6000000-0000-0000-0000-000000000006', 'e5000000-0000-0000-0000-000000000006', 'c3000000-0000-0000-0000-000000000007', 'helpful',     '2024-02-22 10:10:00+00'),
    ('f6000000-0000-0000-0000-000000000007', 'e5000000-0000-0000-0000-000000000008', 'c3000000-0000-0000-0000-000000000006', 'not_helpful', '2024-02-23 11:45:00+00'),
    ('f6000000-0000-0000-0000-000000000008', 'e5000000-0000-0000-0000-000000000008', 'c3000000-0000-0000-0000-000000000001', 'helpful',     '2024-02-23 12:00:00+00'),
    ('f6000000-0000-0000-0000-000000000009', 'e5000000-0000-0000-0000-000000000009', 'c3000000-0000-0000-0000-000000000001', 'not_helpful', '2024-02-24 13:10:00+00'),
    ('f6000000-0000-0000-0000-000000000010', 'e5000000-0000-0000-0000-000000000010', 'c3000000-0000-0000-0000-000000000004', 'not_helpful', '2024-02-25 16:05:00+00')
ON CONFLICT (id) DO NOTHING;
