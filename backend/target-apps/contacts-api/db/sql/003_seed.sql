-- 003_seed.sql
-- Dev/test seed data: 3 departments, 7 contacts (including 1 inactive)
-- Stable UUIDs for reproducible test references. ON CONFLICT DO NOTHING for idempotency.

-- Departments
INSERT INTO departments (id, name, code, created_at) VALUES
    ('a1b2c3d4-0001-4000-8000-000000000001', 'Engineering', 'ENG', '2024-01-15 09:00:00+00'),
    ('a1b2c3d4-0002-4000-8000-000000000002', 'Sales', 'SALES', '2024-01-15 09:00:00+00'),
    ('a1b2c3d4-0003-4000-8000-000000000003', 'Human Resources', 'HR', '2024-01-15 09:00:00+00')
ON CONFLICT DO NOTHING;

-- Contacts
INSERT INTO contacts (id, department_id, full_name, email, phone, title, is_active, created_at, updated_at) VALUES
    ('b1c2d3e4-0001-4000-8000-000000000001', 'a1b2c3d4-0001-4000-8000-000000000001', 'Alice Chen', 'alice.chen@example.com', '+1-555-0101', 'Senior Backend Engineer', true, '2024-02-01 10:00:00+00', '2024-02-01 10:00:00+00'),
    ('b1c2d3e4-0002-4000-8000-000000000002', 'a1b2c3d4-0001-4000-8000-000000000001', 'Bob Martinez', 'bob.martinez@example.com', '+1-555-0102', 'DevOps Lead', true, '2024-02-01 10:00:00+00', '2024-02-01 10:00:00+00'),
    ('b1c2d3e4-0003-4000-8000-000000000003', 'a1b2c3d4-0002-4000-8000-000000000002', 'Carol Johnson', 'carol.johnson@example.com', '+1-555-0201', 'Account Executive', true, '2024-02-05 11:00:00+00', '2024-02-05 11:00:00+00'),
    ('b1c2d3e4-0004-4000-8000-000000000004', 'a1b2c3d4-0002-4000-8000-000000000002', 'David Kim', 'david.kim@example.com', '+1-555-0202', 'Sales Development Rep', true, '2024-02-05 11:00:00+00', '2024-02-05 11:00:00+00'),
    ('b1c2d3e4-0005-4000-8000-000000000005', 'a1b2c3d4-0003-4000-8000-000000000003', 'Eva Novak', 'eva.novak@example.com', '+1-555-0301', 'HR Business Partner', true, '2024-02-10 08:30:00+00', '2024-02-10 08:30:00+00'),
    ('b1c2d3e4-0006-4000-8000-000000000006', 'a1b2c3d4-0001-4000-8000-000000000001', 'Frank Osei', 'frank.osei@example.com', NULL, 'Junior Developer', true, '2024-03-01 14:00:00+00', '2024-03-01 14:00:00+00'),
    ('b1c2d3e4-0007-4000-8000-000000000007', 'a1b2c3d4-0002-4000-8000-000000000002', 'Grace Lee', 'grace.lee@example.com', '+1-555-0203', 'Regional Sales Manager', false, '2024-01-20 09:00:00+00', '2024-04-15 16:00:00+00')
ON CONFLICT DO NOTHING;
