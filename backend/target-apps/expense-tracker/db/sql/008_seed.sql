-- Password for all seed users: "ExpenseTest123!"
-- 008_seed.sql -- Dev/test fixture data

-- ============================================================
-- Teams (5 rows)
-- ============================================================
INSERT INTO teams (id, name, description, created_at) VALUES
    ('a1b2c3d4-0001-4000-8000-000000000001', 'Engineering', 'Software engineering team', now()),
    ('a1b2c3d4-0002-4000-8000-000000000002', 'Marketing', 'Marketing and comms team', now()),
    ('a1b2c3d4-0003-4000-8000-000000000003', 'Finance', 'Finance and accounting team', now()),
    ('a1b2c3d4-0004-4000-8000-000000000004', 'Sales', 'Sales and business development', now()),
    ('a1b2c3d4-0005-4000-8000-000000000005', 'Operations', 'Operations and logistics', now())
ON CONFLICT DO NOTHING;

-- ============================================================
-- Users (7 rows: 2 admin, 1 manager, 4 employees)
-- ============================================================
INSERT INTO users (id, email, role, team_id, token_hash, created_at) VALUES
    ('b1b2c3d4-0001-4000-8000-000000000001', 'admin@example.com', 'admin', 'a1b2c3d4-0001-4000-8000-000000000001', '__BCRYPT_PLACEHOLDER__', now()),
    ('b1b2c3d4-0002-4000-8000-000000000002', 'admin2@example.com', 'admin', 'a1b2c3d4-0003-4000-8000-000000000003', '__BCRYPT_PLACEHOLDER__', now()),
    ('b1b2c3d4-0003-4000-8000-000000000003', 'manager@example.com', 'manager', 'a1b2c3d4-0001-4000-8000-000000000001', '__BCRYPT_PLACEHOLDER__', now()),
    ('b1b2c3d4-0004-4000-8000-000000000004', 'alice@example.com', 'employee', 'a1b2c3d4-0001-4000-8000-000000000001', '__BCRYPT_PLACEHOLDER__', now()),
    ('b1b2c3d4-0005-4000-8000-000000000005', 'bob@example.com', 'employee', 'a1b2c3d4-0001-4000-8000-000000000001', '__BCRYPT_PLACEHOLDER__', now()),
    ('b1b2c3d4-0006-4000-8000-000000000006', 'carol@example.com', 'employee', 'a1b2c3d4-0002-4000-8000-000000000002', '__BCRYPT_PLACEHOLDER__', now()),
    ('b1b2c3d4-0007-4000-8000-000000000007', 'dave@example.com', 'employee', 'a1b2c3d4-0004-4000-8000-000000000004', '__BCRYPT_PLACEHOLDER__', now())
ON CONFLICT DO NOTHING;

-- ============================================================
-- API Keys (5 rows: 2 admin, 2 manager, 1 revoked)
-- key_hash uses __BCRYPT_PLACEHOLDER__ for dev (materialised by pipeline)
-- ============================================================
INSERT INTO api_keys (id, key_hash, role, description, created_at, revoked_at) VALUES
    ('c1b2c3d4-0001-4000-8000-000000000001', '__BCRYPT_PLACEHOLDER__', 'admin', 'Primary admin key (ADMIN_KEY_DEV)', now(), NULL),
    ('c1b2c3d4-0002-4000-8000-000000000002', '__BCRYPT_PLACEHOLDER__', 'admin', 'Secondary admin key', now(), NULL),
    ('c1b2c3d4-0003-4000-8000-000000000003', '__BCRYPT_PLACEHOLDER__', 'manager', 'Manager key - Engineering', now(), NULL),
    ('c1b2c3d4-0004-4000-8000-000000000004', '__BCRYPT_PLACEHOLDER__', 'manager', 'Manager key - Marketing', now(), NULL),
    ('c1b2c3d4-0005-4000-8000-000000000005', '__BCRYPT_PLACEHOLDER__', 'admin', 'Revoked admin key', now(), '2024-01-15 00:00:00+00')
ON CONFLICT DO NOTHING;

-- ============================================================
-- FX Snapshots (8 rows: USD/GBP/EUR + extras across dates)
-- ============================================================
INSERT INTO fx_snapshots (id, currency, date, rate_to_usd) VALUES
    ('d1b2c3d4-0001-4000-8000-000000000001', 'USD', '2024-06-01', 1.0000),
    ('d1b2c3d4-0002-4000-8000-000000000002', 'GBP', '2024-06-01', 1.2700),
    ('d1b2c3d4-0003-4000-8000-000000000003', 'EUR', '2024-06-01', 1.0900),
    ('d1b2c3d4-0004-4000-8000-000000000004', 'USD', '2024-06-15', 1.0000),
    ('d1b2c3d4-0005-4000-8000-000000000005', 'GBP', '2024-06-15', 1.2650),
    ('d1b2c3d4-0006-4000-8000-000000000006', 'EUR', '2024-06-15', 1.0850),
    ('d1b2c3d4-0007-4000-8000-000000000007', 'CAD', '2024-06-01', 0.7350),
    ('d1b2c3d4-0008-4000-8000-000000000008', 'JPY', '2024-06-01', 0.0064)
ON CONFLICT DO NOTHING;

-- ============================================================
-- Expenses (10 rows: mix of statuses, teams, currencies)
-- ============================================================
INSERT INTO expenses (id, user_id, team_id, amount, currency, amount_usd, category, description, expense_date, status, reason, created_at, updated_at) VALUES
    ('e1b2c3d4-0001-4000-8000-000000000001', 'b1b2c3d4-0004-4000-8000-000000000004', 'a1b2c3d4-0001-4000-8000-000000000001', 150.0000, 'GBP', 190.5000, 'travel', 'Train ticket London to Manchester', '2024-06-01', 'approved', 'Approved - valid business trip', now(), now()),
    ('e1b2c3d4-0002-4000-8000-000000000002', 'b1b2c3d4-0004-4000-8000-000000000004', 'a1b2c3d4-0001-4000-8000-000000000001', 45.5000, 'GBP', 57.7850, 'meals', 'Team lunch with client', '2024-06-01', 'submitted', NULL, now(), NULL),
    ('e1b2c3d4-0003-4000-8000-000000000003', 'b1b2c3d4-0005-4000-8000-000000000005', 'a1b2c3d4-0001-4000-8000-000000000001', 299.0000, 'USD', 299.0000, 'software', 'Annual IDE license renewal', '2024-06-15', 'approved', NULL, now(), now()),
    ('e1b2c3d4-0004-4000-8000-000000000004', 'b1b2c3d4-0005-4000-8000-000000000005', 'a1b2c3d4-0001-4000-8000-000000000001', 25.0000, 'USD', 25.0000, 'other', 'Parking at client site', '2024-06-15', 'rejected', 'Not a reimbursable expense', now(), now()),
    ('e1b2c3d4-0005-4000-8000-000000000005', 'b1b2c3d4-0006-4000-8000-000000000006', 'a1b2c3d4-0002-4000-8000-000000000002', 500.0000, 'EUR', 545.0000, 'travel', 'Flight to Berlin conference', '2024-06-01', 'approved', 'Conference attendance approved', now(), now()),
    ('e1b2c3d4-0006-4000-8000-000000000006', 'b1b2c3d4-0006-4000-8000-000000000006', 'a1b2c3d4-0002-4000-8000-000000000002', 78.0000, 'EUR', 85.0200, 'meals', 'Dinner at conference', '2024-06-01', 'submitted', NULL, now(), NULL),
    ('e1b2c3d4-0007-4000-8000-000000000007', 'b1b2c3d4-0007-4000-8000-000000000007', 'a1b2c3d4-0004-4000-8000-000000000004', 1200.0000, 'USD', 1200.0000, 'travel', 'Client visit flight domestic', '2024-06-15', 'submitted', NULL, now(), NULL),
    ('e1b2c3d4-0008-4000-8000-000000000008', 'b1b2c3d4-0004-4000-8000-000000000004', 'a1b2c3d4-0001-4000-8000-000000000001', 19.9900, 'USD', 19.9900, 'software', 'Monthly cloud storage', '2024-06-15', 'approved', NULL, now(), now()),
    ('e1b2c3d4-0009-4000-8000-000000000009', 'b1b2c3d4-0005-4000-8000-000000000005', 'a1b2c3d4-0001-4000-8000-000000000001', 62.0000, 'GBP', 78.4300, 'meals', 'Working lunch with vendor', '2024-06-15', 'submitted', NULL, now(), NULL),
    ('e1b2c3d4-000a-4000-8000-000000000010', 'b1b2c3d4-0007-4000-8000-000000000007', 'a1b2c3d4-0004-4000-8000-000000000004', 350.0000, 'CAD', 257.2500, 'other', 'Conference registration fee', '2024-06-01', 'approved', 'Valid professional development', now(), now())
ON CONFLICT DO NOTHING;

-- ============================================================
-- Audit Log (10 rows: covering various actions)
-- ============================================================
INSERT INTO audit_log (id, expense_id, actor_id, actor_role, action, from_status, to_status, metadata, created_at) VALUES
    ('f1b2c3d4-0001-4000-8000-000000000001', 'e1b2c3d4-0001-4000-8000-000000000001', 'b1b2c3d4-0004-4000-8000-000000000004', 'employee', 'created', NULL, 'submitted', '{"amount": 150.00, "currency": "GBP"}'::jsonb, '2024-06-01 09:00:00+00'),
    ('f1b2c3d4-0002-4000-8000-000000000002', 'e1b2c3d4-0001-4000-8000-000000000001', 'b1b2c3d4-0001-4000-8000-000000000001', 'admin', 'status_changed', 'submitted', 'approved', '{"reason": "Approved - valid business trip"}'::jsonb, '2024-06-02 14:30:00+00'),
    ('f1b2c3d4-0003-4000-8000-000000000003', 'e1b2c3d4-0002-4000-8000-000000000002', 'b1b2c3d4-0004-4000-8000-000000000004', 'employee', 'created', NULL, 'submitted', '{"amount": 45.50, "currency": "GBP"}'::jsonb, '2024-06-01 12:00:00+00'),
    ('f1b2c3d4-0004-4000-8000-000000000004', 'e1b2c3d4-0003-4000-8000-000000000003', 'b1b2c3d4-0005-4000-8000-000000000005', 'employee', 'created', NULL, 'submitted', '{"amount": 299.00, "currency": "USD"}'::jsonb, '2024-06-15 10:00:00+00'),
    ('f1b2c3d4-0005-4000-8000-000000000005', 'e1b2c3d4-0003-4000-8000-000000000003', 'b1b2c3d4-0001-4000-8000-000000000001', 'admin', 'status_changed', 'submitted', 'approved', NULL, '2024-06-15 16:00:00+00'),
    ('f1b2c3d4-0006-4000-8000-000000000006', 'e1b2c3d4-0004-4000-8000-000000000004', 'b1b2c3d4-0005-4000-8000-000000000005', 'employee', 'created', NULL, 'submitted', '{"amount": 25.00, "currency": "USD"}'::jsonb, '2024-06-15 11:00:00+00'),
    ('f1b2c3d4-0007-4000-8000-000000000007', 'e1b2c3d4-0004-4000-8000-000000000004', 'b1b2c3d4-0001-4000-8000-000000000001', 'admin', 'status_changed', 'submitted', 'rejected', '{"reason": "Not a reimbursable expense"}'::jsonb, '2024-06-16 09:00:00+00'),
    ('f1b2c3d4-0008-4000-8000-000000000008', 'e1b2c3d4-0005-4000-8000-000000000005', 'b1b2c3d4-0006-4000-8000-000000000006', 'employee', 'created', NULL, 'submitted', '{"amount": 500.00, "currency": "EUR"}'::jsonb, '2024-06-01 08:00:00+00'),
    ('f1b2c3d4-0009-4000-8000-000000000009', 'e1b2c3d4-0005-4000-8000-000000000005', 'b1b2c3d4-0002-4000-8000-000000000002', 'admin', 'status_changed', 'submitted', 'approved', '{"reason": "Conference attendance approved"}'::jsonb, '2024-06-02 10:00:00+00'),
    ('f1b2c3d4-000a-4000-8000-000000000010', 'e1b2c3d4-000a-4000-8000-000000000010', 'b1b2c3d4-0007-4000-8000-000000000007', 'employee', 'created', NULL, 'submitted', '{"amount": 350.00, "currency": "CAD"}'::jsonb, '2024-06-01 07:30:00+00')
ON CONFLICT DO NOTHING;
