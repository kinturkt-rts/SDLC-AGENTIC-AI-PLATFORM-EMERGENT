-- 008_seed.sql
-- Dev/test seed data for expense-tracker
-- Password for all seed employee tokens: "DevToken123!"
-- Password for all seed api keys: "DevApiKey456!"

-- Teams (5 teams)
INSERT INTO teams (id, name, created_at) VALUES
    (1, 'Engineering', '2024-01-15 09:00:00+00'),
    (2, 'Finance', '2024-01-15 09:05:00+00'),
    (3, 'Marketing', '2024-01-20 10:00:00+00'),
    (4, 'Sales', '2024-01-22 11:00:00+00'),
    (5, 'Operations', '2024-01-25 08:30:00+00')
ON CONFLICT DO NOTHING;

-- Employees (7 employees across teams)
-- token_hash values are distinct SHA-256 hex strings representing hashed bearer tokens
INSERT INTO employees (id, name, team_id, token_hash, role, created_at) VALUES
    (1, 'Alice Johnson', 1, 'a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2', 'employee', '2024-02-01 10:00:00+00'),
    (2, 'Bob Smith', 1, 'b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3', 'employee', '2024-02-01 10:05:00+00'),
    (3, 'Carol Davis', 2, 'c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4', 'employee', '2024-02-01 10:10:00+00'),
    (4, 'David Lee', 3, 'd4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5', 'employee', '2024-02-05 09:00:00+00'),
    (5, 'Eva Martinez', 4, 'e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6', 'employee', '2024-02-05 09:30:00+00'),
    (6, 'Frank Wilson', 5, 'f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7', 'employee', '2024-02-10 08:00:00+00'),
    (7, 'Grace Chen', 1, 'a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8', 'employee', '2024-02-12 10:00:00+00')
ON CONFLICT DO NOTHING;

-- API keys (5 keys: 3 manager, 2 admin)
-- key_hash values are distinct SHA-256 hex strings representing hashed API keys
INSERT INTO api_keys (id, key_hash, role, owner_label, team_ids, created_at) VALUES
    (1, '1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b', 'manager', 'Manager - Engineering', ARRAY[1], '2024-02-01 11:00:00+00'),
    (2, '2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c', 'admin', 'Admin - Global', ARRAY[1,2,3,4,5], '2024-02-01 11:05:00+00'),
    (3, '3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d', 'manager', 'Manager - Finance', ARRAY[2], '2024-02-03 09:00:00+00'),
    (4, '4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e', 'manager', 'Manager - Marketing', ARRAY[3], '2024-02-05 09:00:00+00'),
    (5, '5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f', 'admin', 'Admin - Secondary', ARRAY[1,2,3,4,5], '2024-02-07 10:00:00+00')
ON CONFLICT DO NOTHING;

-- FX rate snapshots (EUR, GBP, CAD for multiple dates in 2024-06)
INSERT INTO fx_rate_snapshots (currency, rate_date, usd_rate, loaded_at) VALUES
    ('EUR', '2024-06-01', 1.085000, '2024-06-01 06:00:00+00'),
    ('EUR', '2024-06-05', 1.087000, '2024-06-05 06:00:00+00'),
    ('EUR', '2024-06-10', 1.082000, '2024-06-10 06:00:00+00'),
    ('EUR', '2024-06-15', 1.080000, '2024-06-15 06:00:00+00'),
    ('EUR', '2024-06-20', 1.090000, '2024-06-20 06:00:00+00'),
    ('GBP', '2024-06-01', 1.270000, '2024-06-01 06:00:00+00'),
    ('GBP', '2024-06-05', 1.272000, '2024-06-05 06:00:00+00'),
    ('GBP', '2024-06-10', 1.268000, '2024-06-10 06:00:00+00'),
    ('GBP', '2024-06-15', 1.265000, '2024-06-15 06:00:00+00'),
    ('GBP', '2024-06-20', 1.275000, '2024-06-20 06:00:00+00'),
    ('CAD', '2024-06-01', 0.735000, '2024-06-01 06:00:00+00'),
    ('CAD', '2024-06-05', 0.738000, '2024-06-05 06:00:00+00'),
    ('CAD', '2024-06-10', 0.732000, '2024-06-10 06:00:00+00'),
    ('CAD', '2024-06-15', 0.730000, '2024-06-15 06:00:00+00'),
    ('CAD', '2024-06-20', 0.740000, '2024-06-20 06:00:00+00')
ON CONFLICT DO NOTHING;

-- Expenses (8 sample expenses in mixed statuses)
-- usd_amount computed: original_amount * usd_rate for the (currency, expense_date)
INSERT INTO expenses (id, employee_id, team_id, original_amount, currency, usd_amount, category, description, expense_date, status, created_at, updated_at) VALUES
    (1, 1, 1, 250.0000, 'EUR', 271.2500, 'travel', 'Flight to Berlin conference', '2024-06-01', 'approved', '2024-06-01 14:00:00+00', '2024-06-02 10:00:00+00'),
    (2, 1, 1, 45.5000, 'GBP', 57.8760, 'meals', 'Client dinner in London', '2024-06-05', 'submitted', '2024-06-05 20:00:00+00', NULL),
    (3, 2, 1, 120.0000, 'CAD', 87.8400, 'software', 'Annual IDE license', '2024-06-10', 'rejected', '2024-06-10 09:30:00+00', '2024-06-11 15:00:00+00'),
    (4, 3, 2, 500.0000, 'EUR', 540.0000, 'travel', 'Train tickets for audit week', '2024-06-15', 'submitted', '2024-06-15 08:00:00+00', NULL),
    (5, 2, 1, 75.0000, 'GBP', 95.6250, 'other', 'Office supplies reimbursement', '2024-06-20', 'approved', '2024-06-20 11:00:00+00', '2024-06-21 09:00:00+00'),
    (6, 4, 3, 300.0000, 'EUR', 327.0000, 'travel', 'Trade show travel expenses', '2024-06-10', 'submitted', '2024-06-10 16:00:00+00', NULL),
    (7, 5, 4, 89.9900, 'CAD', 65.8727, 'software', 'CRM monthly subscription', '2024-06-05', 'approved', '2024-06-05 12:00:00+00', '2024-06-06 09:00:00+00'),
    (8, 6, 5, 200.0000, 'GBP', 253.0000, 'meals', 'Team lunch for onboarding', '2024-06-15', 'rejected', '2024-06-15 13:00:00+00', '2024-06-16 10:00:00+00')
ON CONFLICT DO NOTHING;

-- Audit log entries (creation entry for each expense + transition entries for approved/rejected)
INSERT INTO audit_log (id, expense_id, from_status, to_status, actor_id, actor_role, occurred_at) VALUES
    (1,  1, NULL, 'submitted', 1, 'employee', '2024-06-01 14:00:00+00'),
    (2,  1, 'submitted', 'approved', 2, 'admin', '2024-06-02 10:00:00+00'),
    (3,  2, NULL, 'submitted', 1, 'employee', '2024-06-05 20:00:00+00'),
    (4,  3, NULL, 'submitted', 2, 'employee', '2024-06-10 09:30:00+00'),
    (5,  3, 'submitted', 'rejected', 2, 'admin', '2024-06-11 15:00:00+00'),
    (6,  4, NULL, 'submitted', 3, 'employee', '2024-06-15 08:00:00+00'),
    (7,  5, NULL, 'submitted', 2, 'employee', '2024-06-20 11:00:00+00'),
    (8,  5, 'submitted', 'approved', 2, 'admin', '2024-06-21 09:00:00+00'),
    (9,  6, NULL, 'submitted', 4, 'employee', '2024-06-10 16:00:00+00'),
    (10, 7, NULL, 'submitted', 5, 'employee', '2024-06-05 12:00:00+00'),
    (11, 7, 'submitted', 'approved', 2, 'admin', '2024-06-06 09:00:00+00'),
    (12, 8, NULL, 'submitted', 6, 'employee', '2024-06-15 13:00:00+00'),
    (13, 8, 'submitted', 'rejected', 5, 'admin', '2024-06-16 10:00:00+00')
ON CONFLICT DO NOTHING;

-- Reset sequences to max id
SELECT setval('teams_id_seq', (SELECT COALESCE(MAX(id), 0) FROM teams));
SELECT setval('employees_id_seq', (SELECT COALESCE(MAX(id), 0) FROM employees));
SELECT setval('api_keys_id_seq', (SELECT COALESCE(MAX(id), 0) FROM api_keys));
SELECT setval('expenses_id_seq', (SELECT COALESCE(MAX(id), 0) FROM expenses));
SELECT setval('audit_log_id_seq', (SELECT COALESCE(MAX(id), 0) FROM audit_log));
