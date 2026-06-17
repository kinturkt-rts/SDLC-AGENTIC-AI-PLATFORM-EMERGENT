-- 004_seed.sql
-- Dev/test seed data (idempotent). Stable UUIDs for deterministic test assertions.

SET search_path TO contacts_api;

-- ============================================================
-- Departments (3 rows — Engineering, Sales, HR)
-- ============================================================
INSERT INTO departments (id, name, code, created_at) VALUES
    ('a1b2c3d4-0001-4000-8000-000000000001', 'Engineering', 'ENG',   '2024-01-10 09:00:00+00'),
    ('a1b2c3d4-0002-4000-8000-000000000002', 'Sales',       'SALES', '2024-01-10 09:01:00+00'),
    ('a1b2c3d4-0003-4000-8000-000000000003', 'HR',          'HR',    '2024-01-10 09:02:00+00')
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- Contacts (7 rows — 6 active + 1 inactive; covers all 3 depts)
-- ============================================================
INSERT INTO contacts (id, department_id, full_name, email, phone, title, is_active, created_at, updated_at) VALUES
    ('b2c3d4e5-0001-4000-8000-000000000001',
     'a1b2c3d4-0001-4000-8000-000000000001',
     'Alice Johnson', 'alice.johnson@example.com', '+1-555-0101', 'Senior Engineer', true,
     '2024-02-01 10:00:00+00', '2024-02-01 10:00:00+00'),

    ('b2c3d4e5-0002-4000-8000-000000000002',
     'a1b2c3d4-0001-4000-8000-000000000001',
     'Bob Chen', 'bob.chen@example.com', '+1-555-0102', 'Staff Engineer', true,
     '2024-02-02 11:00:00+00', '2024-02-02 11:00:00+00'),

    ('b2c3d4e5-0003-4000-8000-000000000003',
     'a1b2c3d4-0001-4000-8000-000000000001',
     'Charlie Park', 'charlie.park@example.com', '+1-555-0103', 'Engineering Manager', true,
     '2024-02-03 12:00:00+00', '2024-02-03 12:00:00+00'),

    ('b2c3d4e5-0004-4000-8000-000000000004',
     'a1b2c3d4-0002-4000-8000-000000000002',
     'Diana Rivera', 'diana.rivera@example.com', '+1-555-0201', 'Account Executive', true,
     '2024-02-04 09:00:00+00', '2024-02-04 09:00:00+00'),

    ('b2c3d4e5-0005-4000-8000-000000000005',
     'a1b2c3d4-0002-4000-8000-000000000002',
     'Ethan Williams', 'ethan.williams@example.com', '+1-555-0202', 'Sales Director', true,
     '2024-02-05 14:00:00+00', '2024-02-05 14:00:00+00'),

    ('b2c3d4e5-0006-4000-8000-000000000006',
     'a1b2c3d4-0003-4000-8000-000000000003',
     'Fiona Martinez', 'fiona.martinez@example.com', '+1-555-0301', 'HR Business Partner', true,
     '2024-02-06 08:30:00+00', '2024-02-06 08:30:00+00'),

    ('b2c3d4e5-0007-4000-8000-000000000007',
     'a1b2c3d4-0003-4000-8000-000000000003',
     'George Taylor', 'george.taylor@example.com', '+1-555-0302', 'Recruiter', false,
     '2024-02-07 15:00:00+00', '2024-03-15 11:00:00+00')
ON CONFLICT (id) DO NOTHING;
