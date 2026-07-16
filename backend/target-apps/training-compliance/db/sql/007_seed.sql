-- Password for all seed users: "TrainingPass123!"
-- Seed data for training_compliance schema
-- Covers: 3+ departments, 3+ job roles, 6 courses (mix all-staff + role-specific),
--   16 employees (15 active + 1 inactive), mixed compliance states (COMPLETE, EXPIRED, MISSING, expiring-within-30-days),
--   5 users (one per role + 1 extra employee)
-- All UUIDs are stable for test repeatability. ON CONFLICT DO NOTHING for idempotency.

-- ============================================================
-- DEPARTMENTS (5 rows)
-- ============================================================
INSERT INTO departments (id, name) VALUES
  ('a0000000-0000-4000-8000-000000000001', 'Engineering'),
  ('a0000000-0000-4000-8000-000000000002', 'Operations'),
  ('a0000000-0000-4000-8000-000000000003', 'Finance'),
  ('a0000000-0000-4000-8000-000000000004', 'Human Resources'),
  ('a0000000-0000-4000-8000-000000000005', 'Marketing')
ON CONFLICT DO NOTHING;

-- ============================================================
-- JOB ROLES (5 rows)
-- ============================================================
INSERT INTO job_roles (id, name) VALUES
  ('b0000000-0000-4000-8000-000000000001', 'Software Engineer'),
  ('b0000000-0000-4000-8000-000000000002', 'Operations Analyst'),
  ('b0000000-0000-4000-8000-000000000003', 'Finance Manager'),
  ('b0000000-0000-4000-8000-000000000004', 'HR Specialist'),
  ('b0000000-0000-4000-8000-000000000005', 'Marketing Coordinator')
ON CONFLICT DO NOTHING;

-- ============================================================
-- COURSES (6 rows — safety/security/role_specific, mix of all_staff + role_specific scope)
-- ============================================================
INSERT INTO courses (id, name, category, validity_period_months, scope, reference_field, created_at) VALUES
  ('c0000000-0000-4000-8000-000000000001', 'Workplace Safety Fundamentals',    'safety',        12, 'all_staff',      'https://lms.example.com/ws-001', now() - INTERVAL '90 days'),
  ('c0000000-0000-4000-8000-000000000002', 'Information Security Awareness',   'security',      12, 'all_staff',      'https://lms.example.com/is-002', now() - INTERVAL '85 days'),
  ('c0000000-0000-4000-8000-000000000003', 'Secure Coding Practices',          'role_specific',  6, 'role_specific',  'https://lms.example.com/sc-003', now() - INTERVAL '80 days'),
  ('c0000000-0000-4000-8000-000000000004', 'Financial Regulations Compliance', 'role_specific', 24, 'role_specific',  'https://lms.example.com/fr-004', now() - INTERVAL '75 days'),
  ('c0000000-0000-4000-8000-000000000005', 'Fire Safety & Evacuation',         'safety',        NULL, 'all_staff',    'https://lms.example.com/fs-005', now() - INTERVAL '70 days'),
  ('c0000000-0000-4000-8000-000000000006', 'Data Privacy (GDPR)',              'security',      12, 'role_specific',  'https://lms.example.com/dp-006', now() - INTERVAL '65 days')
ON CONFLICT DO NOTHING;

-- ============================================================
-- ROLE_COURSE_REQUIREMENTS (6 rows)
-- Software Engineers: Secure Coding + Data Privacy
-- Operations Analysts: Fire Safety
-- Finance Managers: Financial Regulations
-- HR Specialists: Data Privacy
-- Marketing Coordinators: Data Privacy
-- ============================================================
INSERT INTO role_course_requirements (id, job_role_id, course_id, assigned_at) VALUES
  ('e0000000-0000-4000-8000-000000000001', 'b0000000-0000-4000-8000-000000000001', 'c0000000-0000-4000-8000-000000000003', now() - INTERVAL '60 days'),
  ('e0000000-0000-4000-8000-000000000002', 'b0000000-0000-4000-8000-000000000001', 'c0000000-0000-4000-8000-000000000006', now() - INTERVAL '60 days'),
  ('e0000000-0000-4000-8000-000000000003', 'b0000000-0000-4000-8000-000000000002', 'c0000000-0000-4000-8000-000000000005', now() - INTERVAL '55 days'),
  ('e0000000-0000-4000-8000-000000000004', 'b0000000-0000-4000-8000-000000000003', 'c0000000-0000-4000-8000-000000000004', now() - INTERVAL '55 days'),
  ('e0000000-0000-4000-8000-000000000005', 'b0000000-0000-4000-8000-000000000004', 'c0000000-0000-4000-8000-000000000006', now() - INTERVAL '50 days'),
  ('e0000000-0000-4000-8000-000000000006', 'b0000000-0000-4000-8000-000000000005', 'c0000000-0000-4000-8000-000000000006', now() - INTERVAL '50 days')
ON CONFLICT DO NOTHING;

-- ============================================================
-- USERS (5 rows — one per role + one extra employee)
-- Note: employee_id will be linked after employees are inserted
-- ============================================================
INSERT INTO users (id, email, hashed_password, role, employee_id) VALUES
  ('10000000-0000-4000-8000-000000000001', 'marcus.chen@example.com',    '__BCRYPT_PLACEHOLDER__', 'hr_admin',            NULL),
  ('10000000-0000-4000-8000-000000000002', 'priya.sharma@example.com',   '__BCRYPT_PLACEHOLDER__', 'manager',             NULL),
  ('10000000-0000-4000-8000-000000000003', 'alice.johnson@example.com',  '__BCRYPT_PLACEHOLDER__', 'employee',            NULL),
  ('10000000-0000-4000-8000-000000000004', 'david.okonkwo@example.com',  '__BCRYPT_PLACEHOLDER__', 'compliance_officer',  NULL),
  ('10000000-0000-4000-8000-000000000005', 'bob.williams@example.com',   '__BCRYPT_PLACEHOLDER__', 'employee',            NULL)
ON CONFLICT DO NOTHING;

-- ============================================================
-- EMPLOYEES (16 rows: 15 active + 1 inactive)
-- Managers first (no manager_id), then reports
-- ============================================================
INSERT INTO employees (id, full_name, email, department_id, job_role_id, manager_id, is_active, user_account_id) VALUES
  ('d0000000-0000-4000-8000-000000000001', 'Marcus Chen',      'marcus.chen@example.com',      'a0000000-0000-4000-8000-000000000004', 'b0000000-0000-4000-8000-000000000004', NULL, true, '10000000-0000-4000-8000-000000000001'),
  ('d0000000-0000-4000-8000-000000000002', 'Priya Sharma',     'priya.sharma@example.com',     'a0000000-0000-4000-8000-000000000001', 'b0000000-0000-4000-8000-000000000001', NULL, true, '10000000-0000-4000-8000-000000000002'),
  ('d0000000-0000-4000-8000-000000000003', 'David Okonkwo',    'david.okonkwo@example.com',    'a0000000-0000-4000-8000-000000000003', 'b0000000-0000-4000-8000-000000000003', NULL, true, NULL)
ON CONFLICT DO NOTHING;

INSERT INTO employees (id, full_name, email, department_id, job_role_id, manager_id, is_active, user_account_id) VALUES
  ('d0000000-0000-4000-8000-000000000004', 'Alice Johnson',    'alice.johnson@example.com',    'a0000000-0000-4000-8000-000000000001', 'b0000000-0000-4000-8000-000000000001', 'd0000000-0000-4000-8000-000000000002', true, '10000000-0000-4000-8000-000000000003'),
  ('d0000000-0000-4000-8000-000000000005', 'Bob Williams',     'bob.williams@example.com',     'a0000000-0000-4000-8000-000000000001', 'b0000000-0000-4000-8000-000000000001', 'd0000000-0000-4000-8000-000000000002', true, '10000000-0000-4000-8000-000000000005'),
  ('d0000000-0000-4000-8000-000000000006', 'Carol Martinez',   'carol.martinez@example.com',   'a0000000-0000-4000-8000-000000000002', 'b0000000-0000-4000-8000-000000000002', 'd0000000-0000-4000-8000-000000000001', true, NULL),
  ('d0000000-0000-4000-8000-000000000007', 'Derek Thompson',   'derek.thompson@example.com',   'a0000000-0000-4000-8000-000000000002', 'b0000000-0000-4000-8000-000000000002', 'd0000000-0000-4000-8000-000000000001', true, NULL),
  ('d0000000-0000-4000-8000-000000000008', 'Elena Rodriguez',  'elena.rodriguez@example.com',  'a0000000-0000-4000-8000-000000000003', 'b0000000-0000-4000-8000-000000000003', 'd0000000-0000-4000-8000-000000000003', true, NULL),
  ('d0000000-0000-4000-8000-000000000009', 'Frank Nguyen',     'frank.nguyen@example.com',     'a0000000-0000-4000-8000-000000000003', 'b0000000-0000-4000-8000-000000000003', 'd0000000-0000-4000-8000-000000000003', true, NULL),
  ('d0000000-0000-4000-8000-000000000010', 'Grace Kim',        'grace.kim@example.com',        'a0000000-0000-4000-8000-000000000001', 'b0000000-0000-4000-8000-000000000001', 'd0000000-0000-4000-8000-000000000002', true, NULL),
  ('d0000000-0000-4000-8000-000000000011', 'Hassan Ali',       'hassan.ali@example.com',       'a0000000-0000-4000-8000-000000000004', 'b0000000-0000-4000-8000-000000000004', 'd0000000-0000-4000-8000-000000000001', true, NULL),
  ('d0000000-0000-4000-8000-000000000012', 'Iris Patel',       'iris.patel@example.com',       'a0000000-0000-4000-8000-000000000005', 'b0000000-0000-4000-8000-000000000005', 'd0000000-0000-4000-8000-000000000001', true, NULL),
  ('d0000000-0000-4000-8000-000000000013', 'James Cooper',     'james.cooper@example.com',     'a0000000-0000-4000-8000-000000000002', 'b0000000-0000-4000-8000-000000000002', 'd0000000-0000-4000-8000-000000000001', true, NULL),
  ('d0000000-0000-4000-8000-000000000014', 'Karen Liu',        'karen.liu@example.com',        'a0000000-0000-4000-8000-000000000001', 'b0000000-0000-4000-8000-000000000001', 'd0000000-0000-4000-8000-000000000002', true, NULL),
  ('d0000000-0000-4000-8000-000000000015', 'Liam O''Brien',    'liam.obrien@example.com',      'a0000000-0000-4000-8000-000000000003', 'b0000000-0000-4000-8000-000000000003', 'd0000000-0000-4000-8000-000000000003', true, NULL)
ON CONFLICT DO NOTHING;

-- Inactive employee
INSERT INTO employees (id, full_name, email, department_id, job_role_id, manager_id, is_active, user_account_id) VALUES
  ('d0000000-0000-4000-8000-000000000016', 'Nina Torres',      'nina.torres@example.com',      'a0000000-0000-4000-8000-000000000002', 'b0000000-0000-4000-8000-000000000002', 'd0000000-0000-4000-8000-000000000001', false, NULL)
ON CONFLICT DO NOTHING;

-- Link users.employee_id back to employees
UPDATE users SET employee_id = 'd0000000-0000-4000-8000-000000000001' WHERE id = '10000000-0000-4000-8000-000000000001';
UPDATE users SET employee_id = 'd0000000-0000-4000-8000-000000000002' WHERE id = '10000000-0000-4000-8000-000000000002';
UPDATE users SET employee_id = 'd0000000-0000-4000-8000-000000000004' WHERE id = '10000000-0000-4000-8000-000000000003';
UPDATE users SET employee_id = NULL WHERE id = '10000000-0000-4000-8000-000000000004';
UPDATE users SET employee_id = 'd0000000-0000-4000-8000-000000000005' WHERE id = '10000000-0000-4000-8000-000000000005';

-- ============================================================
-- COMPLETION RECORDS
-- Mix of: COMPLETE, EXPIRED, expiring-within-30-days, MISSING (implicit), superseded
-- Karen (d...14) and Liam (d...15) have NO completions → MISSING status
-- ============================================================

-- Alice: COMPLETE — Workplace Safety (expires in 8 months)
INSERT INTO completion_records (id, employee_id, course_id, completion_date, expiry_date, is_superseded, recorded_by, created_at) VALUES
  ('f0000000-0000-4000-8000-000000000001', 'd0000000-0000-4000-8000-000000000004', 'c0000000-0000-4000-8000-000000000001', CURRENT_DATE - INTERVAL '4 months', CURRENT_DATE + INTERVAL '8 months', false, '10000000-0000-4000-8000-000000000001', now() - INTERVAL '4 months'),
  -- Alice: COMPLETE — Info Security (expires in 5 months)
  ('f0000000-0000-4000-8000-000000000002', 'd0000000-0000-4000-8000-000000000004', 'c0000000-0000-4000-8000-000000000002', CURRENT_DATE - INTERVAL '7 months', CURRENT_DATE + INTERVAL '5 months', false, '10000000-0000-4000-8000-000000000001', now() - INTERVAL '7 months'),
  -- Alice: COMPLETE — Secure Coding (expires in 2 months)
  ('f0000000-0000-4000-8000-000000000003', 'd0000000-0000-4000-8000-000000000004', 'c0000000-0000-4000-8000-000000000003', CURRENT_DATE - INTERVAL '4 months', CURRENT_DATE + INTERVAL '2 months', false, '10000000-0000-4000-8000-000000000003', now() - INTERVAL '4 months'),
  -- Alice: COMPLETE — Fire Safety (no expiry, one-time)
  ('f0000000-0000-4000-8000-000000000004', 'd0000000-0000-4000-8000-000000000004', 'c0000000-0000-4000-8000-000000000005', CURRENT_DATE - INTERVAL '10 months', NULL, false, '10000000-0000-4000-8000-000000000001', now() - INTERVAL '10 months')
ON CONFLICT DO NOTHING;

-- Bob: EXPIRED — Workplace Safety (expired 2 months ago)
INSERT INTO completion_records (id, employee_id, course_id, completion_date, expiry_date, is_superseded, recorded_by, created_at) VALUES
  ('f0000000-0000-4000-8000-000000000005', 'd0000000-0000-4000-8000-000000000005', 'c0000000-0000-4000-8000-000000000001', CURRENT_DATE - INTERVAL '14 months', CURRENT_DATE - INTERVAL '2 months', false, '10000000-0000-4000-8000-000000000001', now() - INTERVAL '14 months'),
  -- Bob: expiring in 20 days (Info Security)
  ('f0000000-0000-4000-8000-000000000006', 'd0000000-0000-4000-8000-000000000005', 'c0000000-0000-4000-8000-000000000002', CURRENT_DATE - INTERVAL '11 months', CURRENT_DATE + INTERVAL '20 days', false, '10000000-0000-4000-8000-000000000001', now() - INTERVAL '11 months')
ON CONFLICT DO NOTHING;

-- Carol: expiring in 15 days (Workplace Safety)
INSERT INTO completion_records (id, employee_id, course_id, completion_date, expiry_date, is_superseded, recorded_by, created_at) VALUES
  ('f0000000-0000-4000-8000-000000000007', 'd0000000-0000-4000-8000-000000000006', 'c0000000-0000-4000-8000-000000000001', CURRENT_DATE - INTERVAL '11 months', CURRENT_DATE + INTERVAL '15 days', false, '10000000-0000-4000-8000-000000000001', now() - INTERVAL '11 months'),
  -- Carol: COMPLETE — Info Security
  ('f0000000-0000-4000-8000-000000000008', 'd0000000-0000-4000-8000-000000000006', 'c0000000-0000-4000-8000-000000000002', CURRENT_DATE - INTERVAL '3 months', CURRENT_DATE + INTERVAL '9 months', false, '10000000-0000-4000-8000-000000000001', now() - INTERVAL '3 months')
ON CONFLICT DO NOTHING;

-- Derek: expiring in 10 days (Info Security)
INSERT INTO completion_records (id, employee_id, course_id, completion_date, expiry_date, is_superseded, recorded_by, created_at) VALUES
  ('f0000000-0000-4000-8000-000000000009', 'd0000000-0000-4000-8000-000000000007', 'c0000000-0000-4000-8000-000000000002', CURRENT_DATE - INTERVAL '355 days', CURRENT_DATE + INTERVAL '10 days', false, '10000000-0000-4000-8000-000000000001', now() - INTERVAL '355 days'),
  -- Derek: COMPLETE — Workplace Safety
  ('f0000000-0000-4000-8000-000000000010', 'd0000000-0000-4000-8000-000000000007', 'c0000000-0000-4000-8000-000000000001', CURRENT_DATE - INTERVAL '2 months', CURRENT_DATE + INTERVAL '10 months', false, '10000000-0000-4000-8000-000000000001', now() - INTERVAL '2 months')
ON CONFLICT DO NOTHING;

-- Priya: COMPLETE — model employee (all current)
INSERT INTO completion_records (id, employee_id, course_id, completion_date, expiry_date, is_superseded, recorded_by, created_at) VALUES
  ('f0000000-0000-4000-8000-000000000011', 'd0000000-0000-4000-8000-000000000002', 'c0000000-0000-4000-8000-000000000001', CURRENT_DATE - INTERVAL '1 month', CURRENT_DATE + INTERVAL '11 months', false, '10000000-0000-4000-8000-000000000001', now() - INTERVAL '1 month'),
  ('f0000000-0000-4000-8000-000000000012', 'd0000000-0000-4000-8000-000000000002', 'c0000000-0000-4000-8000-000000000002', CURRENT_DATE - INTERVAL '2 months', CURRENT_DATE + INTERVAL '10 months', false, '10000000-0000-4000-8000-000000000001', now() - INTERVAL '2 months'),
  ('f0000000-0000-4000-8000-000000000013', 'd0000000-0000-4000-8000-000000000002', 'c0000000-0000-4000-8000-000000000003', CURRENT_DATE - INTERVAL '1 month', CURRENT_DATE + INTERVAL '5 months', false, '10000000-0000-4000-8000-000000000002', now() - INTERVAL '1 month'),
  ('f0000000-0000-4000-8000-000000000014', 'd0000000-0000-4000-8000-000000000002', 'c0000000-0000-4000-8000-000000000005', CURRENT_DATE - INTERVAL '6 months', NULL, false, '10000000-0000-4000-8000-000000000001', now() - INTERVAL '6 months')
ON CONFLICT DO NOTHING;

-- Marcus: COMPLETE — Workplace Safety + Info Security + Fire Safety
INSERT INTO completion_records (id, employee_id, course_id, completion_date, expiry_date, is_superseded, recorded_by, created_at) VALUES
  ('f0000000-0000-4000-8000-000000000015', 'd0000000-0000-4000-8000-000000000001', 'c0000000-0000-4000-8000-000000000001', CURRENT_DATE - INTERVAL '3 months', CURRENT_DATE + INTERVAL '9 months', false, '10000000-0000-4000-8000-000000000001', now() - INTERVAL '3 months'),
  ('f0000000-0000-4000-8000-000000000016', 'd0000000-0000-4000-8000-000000000001', 'c0000000-0000-4000-8000-000000000002', CURRENT_DATE - INTERVAL '5 months', CURRENT_DATE + INTERVAL '7 months', false, '10000000-0000-4000-8000-000000000001', now() - INTERVAL '5 months'),
  ('f0000000-0000-4000-8000-000000000017', 'd0000000-0000-4000-8000-000000000001', 'c0000000-0000-4000-8000-000000000005', CURRENT_DATE - INTERVAL '9 months', NULL, false, '10000000-0000-4000-8000-000000000001', now() - INTERVAL '9 months')
ON CONFLICT DO NOTHING;

-- Grace: EXPIRED — Info Security (expired 1 month ago)
INSERT INTO completion_records (id, employee_id, course_id, completion_date, expiry_date, is_superseded, recorded_by, created_at) VALUES
  ('f0000000-0000-4000-8000-000000000018', 'd0000000-0000-4000-8000-000000000010', 'c0000000-0000-4000-8000-000000000002', CURRENT_DATE - INTERVAL '13 months', CURRENT_DATE - INTERVAL '1 month', false, '10000000-0000-4000-8000-000000000001', now() - INTERVAL '13 months'),
  -- Grace: COMPLETE — Workplace Safety
  ('f0000000-0000-4000-8000-000000000019', 'd0000000-0000-4000-8000-000000000010', 'c0000000-0000-4000-8000-000000000001', CURRENT_DATE - INTERVAL '2 months', CURRENT_DATE + INTERVAL '10 months', false, '10000000-0000-4000-8000-000000000001', now() - INTERVAL '2 months')
ON CONFLICT DO NOTHING;

-- Elena & Frank: COMPLETE — Financial Regulations + all-staff courses
INSERT INTO completion_records (id, employee_id, course_id, completion_date, expiry_date, is_superseded, recorded_by, created_at) VALUES
  ('f0000000-0000-4000-8000-000000000020', 'd0000000-0000-4000-8000-000000000008', 'c0000000-0000-4000-8000-000000000004', CURRENT_DATE - INTERVAL '6 months', CURRENT_DATE + INTERVAL '18 months', false, '10000000-0000-4000-8000-000000000001', now() - INTERVAL '6 months'),
  ('f0000000-0000-4000-8000-000000000021', 'd0000000-0000-4000-8000-000000000008', 'c0000000-0000-4000-8000-000000000001', CURRENT_DATE - INTERVAL '4 months', CURRENT_DATE + INTERVAL '8 months', false, '10000000-0000-4000-8000-000000000001', now() - INTERVAL '4 months'),
  ('f0000000-0000-4000-8000-000000000022', 'd0000000-0000-4000-8000-000000000008', 'c0000000-0000-4000-8000-000000000002', CURRENT_DATE - INTERVAL '5 months', CURRENT_DATE + INTERVAL '7 months', false, '10000000-0000-4000-8000-000000000001', now() - INTERVAL '5 months'),
  ('f0000000-0000-4000-8000-000000000023', 'd0000000-0000-4000-8000-000000000009', 'c0000000-0000-4000-8000-000000000004', CURRENT_DATE - INTERVAL '3 months', CURRENT_DATE + INTERVAL '21 months', false, '10000000-0000-4000-8000-000000000001', now() - INTERVAL '3 months'),
  ('f0000000-0000-4000-8000-000000000024', 'd0000000-0000-4000-8000-000000000009', 'c0000000-0000-4000-8000-000000000001', CURRENT_DATE - INTERVAL '2 months', CURRENT_DATE + INTERVAL '10 months', false, '10000000-0000-4000-8000-000000000001', now() - INTERVAL '2 months')
ON CONFLICT DO NOTHING;

-- Nina (inactive): historical completions — retained but excluded from live counts
INSERT INTO completion_records (id, employee_id, course_id, completion_date, expiry_date, is_superseded, recorded_by, created_at) VALUES
  ('f0000000-0000-4000-8000-000000000025', 'd0000000-0000-4000-8000-000000000016', 'c0000000-0000-4000-8000-000000000001', CURRENT_DATE - INTERVAL '18 months', CURRENT_DATE - INTERVAL '6 months', false, '10000000-0000-4000-8000-000000000001', now() - INTERVAL '18 months'),
  ('f0000000-0000-4000-8000-000000000026', 'd0000000-0000-4000-8000-000000000016', 'c0000000-0000-4000-8000-000000000002', CURRENT_DATE - INTERVAL '15 months', CURRENT_DATE - INTERVAL '3 months', false, '10000000-0000-4000-8000-000000000001', now() - INTERVAL '15 months')
ON CONFLICT DO NOTHING;

-- Superseded record example: Priya recertified Secure Coding (old record superseded)
INSERT INTO completion_records (id, employee_id, course_id, completion_date, expiry_date, is_superseded, recorded_by, created_at) VALUES
  ('f0000000-0000-4000-8000-000000000027', 'd0000000-0000-4000-8000-000000000002', 'c0000000-0000-4000-8000-000000000003', CURRENT_DATE - INTERVAL '8 months', CURRENT_DATE - INTERVAL '2 months', true, '10000000-0000-4000-8000-000000000001', now() - INTERVAL '8 months')
ON CONFLICT DO NOTHING;
