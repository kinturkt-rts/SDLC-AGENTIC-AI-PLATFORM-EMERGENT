-- Seed 011: Dev/test fixture data for training_compliance
-- Password for all seed users: "TrainingPass123!"
-- Covers: 3 departments, 3 job roles, 6 courses (mix all-staff + role-specific),
--   16 employees (15 active, 1 inactive), mixed compliance states,
--   >=3 expiring within 30 days, >=2 never-started, 1 user per role.
-- All UUIDs are stable for test repeatability.

-- ============================================================
-- DEPARTMENTS (5 rows - seedMinRows met)
-- ============================================================
INSERT INTO training_compliance.departments (id, name) VALUES
  ('a0000000-0000-4000-8000-000000000001', 'Engineering'),
  ('a0000000-0000-4000-8000-000000000002', 'Operations'),
  ('a0000000-0000-4000-8000-000000000003', 'Finance'),
  ('a0000000-0000-4000-8000-000000000004', 'Human Resources'),
  ('a0000000-0000-4000-8000-000000000005', 'Marketing')
ON CONFLICT DO NOTHING;

-- ============================================================
-- JOB ROLES (5 rows)
-- ============================================================
INSERT INTO training_compliance.job_roles (id, name) VALUES
  ('b0000000-0000-4000-8000-000000000001', 'Software Engineer'),
  ('b0000000-0000-4000-8000-000000000002', 'Operations Analyst'),
  ('b0000000-0000-4000-8000-000000000003', 'Finance Manager'),
  ('b0000000-0000-4000-8000-000000000004', 'HR Specialist'),
  ('b0000000-0000-4000-8000-000000000005', 'Marketing Coordinator')
ON CONFLICT DO NOTHING;

-- ============================================================
-- COURSES (6 rows — safety/security/role_specific, mix of all-staff + validity)
-- ============================================================
INSERT INTO training_compliance.courses (id, name, category, validity_period_months, required_for_all_staff, certificate_ref, is_active) VALUES
  ('c0000000-0000-4000-8000-000000000001', 'Workplace Safety Fundamentals',    'safety',        12, true,  'CERT-WS-001', true),
  ('c0000000-0000-4000-8000-000000000002', 'Information Security Awareness',   'security',      12, true,  'CERT-IS-002', true),
  ('c0000000-0000-4000-8000-000000000003', 'Secure Coding Practices',          'role_specific',  6, false, 'CERT-SC-003', true),
  ('c0000000-0000-4000-8000-000000000004', 'Financial Regulations Compliance', 'role_specific', 24, false, 'CERT-FR-004', true),
  ('c0000000-0000-4000-8000-000000000005', 'Fire Safety & Evacuation',         'safety',        NULL, true, 'CERT-FS-005', true),
  ('c0000000-0000-4000-8000-000000000006', 'Data Privacy (GDPR)',              'security',       12, false, 'CERT-DP-006', true)
ON CONFLICT DO NOTHING;

-- ============================================================
-- EMPLOYEES (16 rows: 15 active + 1 inactive)
-- Managers: Marcus (HR admin), Priya (manager in Engineering)
-- ============================================================
-- Managers first (no manager_id)
INSERT INTO training_compliance.employees (id, full_name, email, department_id, job_role_id, manager_id, is_active) VALUES
  ('d0000000-0000-4000-8000-000000000001', 'Marcus Chen',      'marcus.chen@example.com',      'a0000000-0000-4000-8000-000000000004', 'b0000000-0000-4000-8000-000000000004', NULL, true),
  ('d0000000-0000-4000-8000-000000000002', 'Priya Sharma',     'priya.sharma@example.com',     'a0000000-0000-4000-8000-000000000001', 'b0000000-0000-4000-8000-000000000001', NULL, true),
  ('d0000000-0000-4000-8000-000000000003', 'David Okonkwo',    'david.okonkwo@example.com',    'a0000000-0000-4000-8000-000000000003', 'b0000000-0000-4000-8000-000000000003', NULL, true)
ON CONFLICT DO NOTHING;

-- Reports
INSERT INTO training_compliance.employees (id, full_name, email, department_id, job_role_id, manager_id, is_active) VALUES
  ('d0000000-0000-4000-8000-000000000004', 'Alice Johnson',    'alice.johnson@example.com',    'a0000000-0000-4000-8000-000000000001', 'b0000000-0000-4000-8000-000000000001', 'd0000000-0000-4000-8000-000000000002', true),
  ('d0000000-0000-4000-8000-000000000005', 'Bob Williams',     'bob.williams@example.com',     'a0000000-0000-4000-8000-000000000001', 'b0000000-0000-4000-8000-000000000001', 'd0000000-0000-4000-8000-000000000002', true),
  ('d0000000-0000-4000-8000-000000000006', 'Carol Martinez',   'carol.martinez@example.com',   'a0000000-0000-4000-8000-000000000002', 'b0000000-0000-4000-8000-000000000002', 'd0000000-0000-4000-8000-000000000001', true),
  ('d0000000-0000-4000-8000-000000000007', 'Derek Thompson',   'derek.thompson@example.com',   'a0000000-0000-4000-8000-000000000002', 'b0000000-0000-4000-8000-000000000002', 'd0000000-0000-4000-8000-000000000001', true),
  ('d0000000-0000-4000-8000-000000000008', 'Elena Rodriguez',  'elena.rodriguez@example.com',  'a0000000-0000-4000-8000-000000000003', 'b0000000-0000-4000-8000-000000000003', 'd0000000-0000-4000-8000-000000000003', true),
  ('d0000000-0000-4000-8000-000000000009', 'Frank Nguyen',     'frank.nguyen@example.com',     'a0000000-0000-4000-8000-000000000003', 'b0000000-0000-4000-8000-000000000003', 'd0000000-0000-4000-8000-000000000003', true),
  ('d0000000-0000-4000-8000-000000000010', 'Grace Kim',        'grace.kim@example.com',        'a0000000-0000-4000-8000-000000000001', 'b0000000-0000-4000-8000-000000000001', 'd0000000-0000-4000-8000-000000000002', true),
  ('d0000000-0000-4000-8000-000000000011', 'Hassan Ali',       'hassan.ali@example.com',       'a0000000-0000-4000-8000-000000000004', 'b0000000-0000-4000-8000-000000000004', 'd0000000-0000-4000-8000-000000000001', true),
  ('d0000000-0000-4000-8000-000000000012', 'Iris Patel',       'iris.patel@example.com',       'a0000000-0000-4000-8000-000000000005', 'b0000000-0000-4000-8000-000000000005', 'd0000000-0000-4000-8000-000000000001', true),
  ('d0000000-0000-4000-8000-000000000013', 'James Cooper',     'james.cooper@example.com',     'a0000000-0000-4000-8000-000000000002', 'b0000000-0000-4000-8000-000000000002', 'd0000000-0000-4000-8000-000000000001', true),
  ('d0000000-0000-4000-8000-000000000014', 'Karen Liu',        'karen.liu@example.com',        'a0000000-0000-4000-8000-000000000001', 'b0000000-0000-4000-8000-000000000001', 'd0000000-0000-4000-8000-000000000002', true),
  ('d0000000-0000-4000-8000-000000000015', 'Liam O''Brien',    'liam.obrien@example.com',      'a0000000-0000-4000-8000-000000000003', 'b0000000-0000-4000-8000-000000000003', 'd0000000-0000-4000-8000-000000000003', true)
ON CONFLICT DO NOTHING;

-- Inactive employee (historical completions preserved)
INSERT INTO training_compliance.employees (id, full_name, email, department_id, job_role_id, manager_id, is_active) VALUES
  ('d0000000-0000-4000-8000-000000000016', 'Nina Torres',      'nina.torres@example.com',      'a0000000-0000-4000-8000-000000000002', 'b0000000-0000-4000-8000-000000000002', 'd0000000-0000-4000-8000-000000000001', false)
ON CONFLICT DO NOTHING;

-- ============================================================
-- ROLE REQUIREMENTS (6 rows)
-- Software Engineers need Secure Coding + Data Privacy
-- Operations Analysts need Fire Safety (already all-staff but also role-required)
-- Finance Managers need Financial Regulations
-- ============================================================
INSERT INTO training_compliance.role_requirements (id, job_role_id, course_id) VALUES
  ('e0000000-0000-4000-8000-000000000001', 'b0000000-0000-4000-8000-000000000001', 'c0000000-0000-4000-8000-000000000003'),
  ('e0000000-0000-4000-8000-000000000002', 'b0000000-0000-4000-8000-000000000001', 'c0000000-0000-4000-8000-000000000006'),
  ('e0000000-0000-4000-8000-000000000003', 'b0000000-0000-4000-8000-000000000002', 'c0000000-0000-4000-8000-000000000005'),
  ('e0000000-0000-4000-8000-000000000004', 'b0000000-0000-4000-8000-000000000003', 'c0000000-0000-4000-8000-000000000004'),
  ('e0000000-0000-4000-8000-000000000005', 'b0000000-0000-4000-8000-000000000004', 'c0000000-0000-4000-8000-000000000006'),
  ('e0000000-0000-4000-8000-000000000006', 'b0000000-0000-4000-8000-000000000005', 'c0000000-0000-4000-8000-000000000006')
ON CONFLICT DO NOTHING;

-- ============================================================
-- COMPLETION RECORDS
-- Mix of: current, expired, expiring within 30 days, superseded, never-started (implicit)
-- Using CURRENT_DATE arithmetic for expiry_date to stay realistic.
-- Employees 14 (Karen) and 15 (Liam) have NO completions → "never started"
-- ============================================================

-- Alice: current Workplace Safety (expires in 8 months)
INSERT INTO training_compliance.completion_records (id, employee_id, course_id, completion_date, expiry_date, is_active_record, superseded_by_id) VALUES
  ('f0000000-0000-4000-8000-000000000001', 'd0000000-0000-4000-8000-000000000004', 'c0000000-0000-4000-8000-000000000001', CURRENT_DATE - INTERVAL '4 months', CURRENT_DATE + INTERVAL '8 months', true, NULL),
  -- Alice: current Info Security (expires in 5 months)
  ('f0000000-0000-4000-8000-000000000002', 'd0000000-0000-4000-8000-000000000004', 'c0000000-0000-4000-8000-000000000002', CURRENT_DATE - INTERVAL '7 months', CURRENT_DATE + INTERVAL '5 months', true, NULL),
  -- Alice: current Secure Coding (expires in 2 months)
  ('f0000000-0000-4000-8000-000000000003', 'd0000000-0000-4000-8000-000000000004', 'c0000000-0000-4000-8000-000000000003', CURRENT_DATE - INTERVAL '4 months', CURRENT_DATE + INTERVAL '2 months', true, NULL),
  -- Alice: Fire Safety (no expiry, one-time)
  ('f0000000-0000-4000-8000-000000000004', 'd0000000-0000-4000-8000-000000000004', 'c0000000-0000-4000-8000-000000000005', CURRENT_DATE - INTERVAL '10 months', NULL, true, NULL)
ON CONFLICT DO NOTHING;

-- Bob: expired Workplace Safety (expired 2 months ago) — overdue
INSERT INTO training_compliance.completion_records (id, employee_id, course_id, completion_date, expiry_date, is_active_record, superseded_by_id) VALUES
  ('f0000000-0000-4000-8000-000000000005', 'd0000000-0000-4000-8000-000000000005', 'c0000000-0000-4000-8000-000000000001', CURRENT_DATE - INTERVAL '14 months', CURRENT_DATE - INTERVAL '2 months', true, NULL),
  -- Bob: expiring in 20 days (Info Security)
  ('f0000000-0000-4000-8000-000000000006', 'd0000000-0000-4000-8000-000000000005', 'c0000000-0000-4000-8000-000000000002', CURRENT_DATE - INTERVAL '11 months', CURRENT_DATE + INTERVAL '20 days', true, NULL)
ON CONFLICT DO NOTHING;

-- Carol: expiring in 15 days (Workplace Safety)
INSERT INTO training_compliance.completion_records (id, employee_id, course_id, completion_date, expiry_date, is_active_record, superseded_by_id) VALUES
  ('f0000000-0000-4000-8000-000000000007', 'd0000000-0000-4000-8000-000000000006', 'c0000000-0000-4000-8000-000000000001', CURRENT_DATE - INTERVAL '11 months', CURRENT_DATE + INTERVAL '15 days', true, NULL),
  -- Carol: current Info Security
  ('f0000000-0000-4000-8000-000000000008', 'd0000000-0000-4000-8000-000000000006', 'c0000000-0000-4000-8000-000000000002', CURRENT_DATE - INTERVAL '3 months', CURRENT_DATE + INTERVAL '9 months', true, NULL)
ON CONFLICT DO NOTHING;

-- Derek: expiring in 10 days (Info Security)
INSERT INTO training_compliance.completion_records (id, employee_id, course_id, completion_date, expiry_date, is_active_record, superseded_by_id) VALUES
  ('f0000000-0000-4000-8000-000000000009', 'd0000000-0000-4000-8000-000000000007', 'c0000000-0000-4000-8000-000000000002', CURRENT_DATE - INTERVAL '355 days', CURRENT_DATE + INTERVAL '10 days', true, NULL),
  -- Derek: current Workplace Safety
  ('f0000000-0000-4000-8000-000000000010', 'd0000000-0000-4000-8000-000000000007', 'c0000000-0000-4000-8000-000000000001', CURRENT_DATE - INTERVAL '2 months', CURRENT_DATE + INTERVAL '10 months', true, NULL)
ON CONFLICT DO NOTHING;

-- Priya: current everything (model employee)
INSERT INTO training_compliance.completion_records (id, employee_id, course_id, completion_date, expiry_date, is_active_record, superseded_by_id) VALUES
  ('f0000000-0000-4000-8000-000000000011', 'd0000000-0000-4000-8000-000000000002', 'c0000000-0000-4000-8000-000000000001', CURRENT_DATE - INTERVAL '1 month', CURRENT_DATE + INTERVAL '11 months', true, NULL),
  ('f0000000-0000-4000-8000-000000000012', 'd0000000-0000-4000-8000-000000000002', 'c0000000-0000-4000-8000-000000000002', CURRENT_DATE - INTERVAL '2 months', CURRENT_DATE + INTERVAL '10 months', true, NULL),
  ('f0000000-0000-4000-8000-000000000013', 'd0000000-0000-4000-8000-000000000002', 'c0000000-0000-4000-8000-000000000003', CURRENT_DATE - INTERVAL '1 month', CURRENT_DATE + INTERVAL '5 months', true, NULL),
  ('f0000000-0000-4000-8000-000000000014', 'd0000000-0000-4000-8000-000000000002', 'c0000000-0000-4000-8000-000000000005', CURRENT_DATE - INTERVAL '6 months', NULL, true, NULL)
ON CONFLICT DO NOTHING;

-- Marcus: current Workplace Safety + Info Security
INSERT INTO training_compliance.completion_records (id, employee_id, course_id, completion_date, expiry_date, is_active_record, superseded_by_id) VALUES
  ('f0000000-0000-4000-8000-000000000015', 'd0000000-0000-4000-8000-000000000001', 'c0000000-0000-4000-8000-000000000001', CURRENT_DATE - INTERVAL '3 months', CURRENT_DATE + INTERVAL '9 months', true, NULL),
  ('f0000000-0000-4000-8000-000000000016', 'd0000000-0000-4000-8000-000000000001', 'c0000000-0000-4000-8000-000000000002', CURRENT_DATE - INTERVAL '5 months', CURRENT_DATE + INTERVAL '7 months', true, NULL),
  ('f0000000-0000-4000-8000-000000000017', 'd0000000-0000-4000-8000-000000000001', 'c0000000-0000-4000-8000-000000000005', CURRENT_DATE - INTERVAL '9 months', NULL, true, NULL)
ON CONFLICT DO NOTHING;

-- Grace: expired Info Security (expired 1 month ago) — overdue
INSERT INTO training_compliance.completion_records (id, employee_id, course_id, completion_date, expiry_date, is_active_record, superseded_by_id) VALUES
  ('f0000000-0000-4000-8000-000000000018', 'd0000000-0000-4000-8000-000000000010', 'c0000000-0000-4000-8000-000000000002', CURRENT_DATE - INTERVAL '13 months', CURRENT_DATE - INTERVAL '1 month', true, NULL),
  -- Grace: current Workplace Safety
  ('f0000000-0000-4000-8000-000000000019', 'd0000000-0000-4000-8000-000000000010', 'c0000000-0000-4000-8000-000000000001', CURRENT_DATE - INTERVAL '2 months', CURRENT_DATE + INTERVAL '10 months', true, NULL)
ON CONFLICT DO NOTHING;

-- Elena & Frank: current Finance Regs
INSERT INTO training_compliance.completion_records (id, employee_id, course_id, completion_date, expiry_date, is_active_record, superseded_by_id) VALUES
  ('f0000000-0000-4000-8000-000000000020', 'd0000000-0000-4000-8000-000000000008', 'c0000000-0000-4000-8000-000000000004', CURRENT_DATE - INTERVAL '6 months', CURRENT_DATE + INTERVAL '18 months', true, NULL),
  ('f0000000-0000-4000-8000-000000000021', 'd0000000-0000-4000-8000-000000000008', 'c0000000-0000-4000-8000-000000000001', CURRENT_DATE - INTERVAL '4 months', CURRENT_DATE + INTERVAL '8 months', true, NULL),
  ('f0000000-0000-4000-8000-000000000022', 'd0000000-0000-4000-8000-000000000008', 'c0000000-0000-4000-8000-000000000002', CURRENT_DATE - INTERVAL '5 months', CURRENT_DATE + INTERVAL '7 months', true, NULL),
  ('f0000000-0000-4000-8000-000000000023', 'd0000000-0000-4000-8000-000000000009', 'c0000000-0000-4000-8000-000000000004', CURRENT_DATE - INTERVAL '3 months', CURRENT_DATE + INTERVAL '21 months', true, NULL),
  ('f0000000-0000-4000-8000-000000000024', 'd0000000-0000-4000-8000-000000000009', 'c0000000-0000-4000-8000-000000000001', CURRENT_DATE - INTERVAL '2 months', CURRENT_DATE + INTERVAL '10 months', true, NULL)
ON CONFLICT DO NOTHING;

-- Nina (inactive): historical completion — retained but excluded from live counts
INSERT INTO training_compliance.completion_records (id, employee_id, course_id, completion_date, expiry_date, is_active_record, superseded_by_id) VALUES
  ('f0000000-0000-4000-8000-000000000025', 'd0000000-0000-4000-8000-000000000016', 'c0000000-0000-4000-8000-000000000001', CURRENT_DATE - INTERVAL '18 months', CURRENT_DATE - INTERVAL '6 months', true, NULL),
  ('f0000000-0000-4000-8000-000000000026', 'd0000000-0000-4000-8000-000000000016', 'c0000000-0000-4000-8000-000000000002', CURRENT_DATE - INTERVAL '15 months', CURRENT_DATE - INTERVAL '3 months', true, NULL)
ON CONFLICT DO NOTHING;

-- Superseded record example: Priya recertified Secure Coding (old record)
INSERT INTO training_compliance.completion_records (id, employee_id, course_id, completion_date, expiry_date, is_active_record, superseded_by_id) VALUES
  ('f0000000-0000-4000-8000-000000000027', 'd0000000-0000-4000-8000-000000000002', 'c0000000-0000-4000-8000-000000000003', CURRENT_DATE - INTERVAL '8 months', CURRENT_DATE - INTERVAL '2 months', false, 'f0000000-0000-4000-8000-000000000013')
ON CONFLICT DO NOTHING;

-- ============================================================
-- USERS (5 rows — one per role + one extra employee)
-- Password for all seed users: "TrainingPass123!"
-- ============================================================
INSERT INTO training_compliance.users (id, employee_id, email, hashed_password, role) VALUES
  ('10000000-0000-4000-8000-000000000001', 'd0000000-0000-4000-8000-000000000001', 'marcus.chen@example.com',    '__BCRYPT_PLACEHOLDER__', 'hr_admin'),
  ('10000000-0000-4000-8000-000000000002', 'd0000000-0000-4000-8000-000000000002', 'priya.sharma@example.com',   '__BCRYPT_PLACEHOLDER__', 'manager'),
  ('10000000-0000-4000-8000-000000000003', 'd0000000-0000-4000-8000-000000000004', 'alice.johnson@example.com',  '__BCRYPT_PLACEHOLDER__', 'employee'),
  ('10000000-0000-4000-8000-000000000004', 'd0000000-0000-4000-8000-000000000003', 'david.okonkwo@example.com',  '__BCRYPT_PLACEHOLDER__', 'compliance_officer'),
  ('10000000-0000-4000-8000-000000000005', 'd0000000-0000-4000-8000-000000000005', 'bob.williams@example.com',   '__BCRYPT_PLACEHOLDER__', 'employee')
ON CONFLICT DO NOTHING;

-- ============================================================
-- AUDIT_LOG (5 rows — sample entries)
-- ============================================================
INSERT INTO training_compliance.audit_log (id, user_id, action, entity, entity_id, timestamp, detail) VALUES
  ('aa000000-0000-4000-8000-000000000001', '10000000-0000-4000-8000-000000000001', 'CREATE', 'course', 'c0000000-0000-4000-8000-000000000001', now() - INTERVAL '30 days', '{"name":"Workplace Safety Fundamentals"}'),
  ('aa000000-0000-4000-8000-000000000002', '10000000-0000-4000-8000-000000000001', 'CREATE', 'employee', 'd0000000-0000-4000-8000-000000000004', now() - INTERVAL '28 days', '{"full_name":"Alice Johnson"}'),
  ('aa000000-0000-4000-8000-000000000003', '10000000-0000-4000-8000-000000000001', 'CREATE', 'completion_record', 'f0000000-0000-4000-8000-000000000001', now() - INTERVAL '25 days', '{"employee":"Alice Johnson","course":"Workplace Safety Fundamentals"}'),
  ('aa000000-0000-4000-8000-000000000004', '10000000-0000-4000-8000-000000000001', 'DEACTIVATE', 'employee', 'd0000000-0000-4000-8000-000000000016', now() - INTERVAL '10 days', '{"full_name":"Nina Torres","reason":"departed"}'),
  ('aa000000-0000-4000-8000-000000000005', '10000000-0000-4000-8000-000000000003', 'CREATE', 'completion_record', 'f0000000-0000-4000-8000-000000000003', now() - INTERVAL '20 days', '{"employee":"Alice Johnson","course":"Secure Coding Practices","self_reported":true}')
ON CONFLICT DO NOTHING;
