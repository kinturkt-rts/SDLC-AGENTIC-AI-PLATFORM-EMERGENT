-- Password for all seed users: "BenefitsDemo1!"
-- Dev/test seed data for Benefits Q&A Desk

-- ===== USERS (5 rows) =====
INSERT INTO users (id, username, hashed_password, role, is_active, created_at) VALUES
    ('a1b2c3d4-0001-4000-8000-000000000001', 'admin', '__BCRYPT_PLACEHOLDER__', 'admin', TRUE, '2025-01-10 09:00:00+00'),
    ('a1b2c3d4-0002-4000-8000-000000000002', 'hr_contributor', '__BCRYPT_PLACEHOLDER__', 'contributor', TRUE, '2025-01-10 09:05:00+00'),
    ('a1b2c3d4-0003-4000-8000-000000000003', 'employee1', '__BCRYPT_PLACEHOLDER__', 'employee', TRUE, '2025-01-11 10:00:00+00'),
    ('a1b2c3d4-0004-4000-8000-000000000004', 'employee2', '__BCRYPT_PLACEHOLDER__', 'employee', TRUE, '2025-01-12 08:30:00+00'),
    ('a1b2c3d4-0005-4000-8000-000000000005', 'hr_manager', '__BCRYPT_PLACEHOLDER__', 'contributor', TRUE, '2025-01-13 11:00:00+00')
ON CONFLICT (id) DO NOTHING;

-- ===== COLLECTIONS (5 rows) =====
INSERT INTO collections (id, name, description, created_by, created_at, updated_at) VALUES
    ('b1b2c3d4-0001-4000-8000-000000000001', '2026 Benefits Demo', 'Demo collection for 2026 open enrollment benefit documents', 'a1b2c3d4-0002-4000-8000-000000000002', '2025-01-15 10:00:00+00', '2025-01-15 10:00:00+00'),
    ('b1b2c3d4-0002-4000-8000-000000000002', 'Dental & Vision Plans', 'Documents covering dental and vision insurance options', 'a1b2c3d4-0002-4000-8000-000000000002', '2025-01-16 09:00:00+00', '2025-01-16 09:00:00+00'),
    ('b1b2c3d4-0003-4000-8000-000000000003', 'Retirement & 401k', 'Retirement plan documentation and guides', 'a1b2c3d4-0005-4000-8000-000000000005', '2025-01-17 14:00:00+00', '2025-01-17 14:00:00+00'),
    ('b1b2c3d4-0004-4000-8000-000000000004', 'Parental Leave Policy', 'Maternity and paternity leave guidelines', 'a1b2c3d4-0005-4000-8000-000000000005', '2025-01-18 11:00:00+00', '2025-01-18 11:00:00+00'),
    ('b1b2c3d4-0005-4000-8000-000000000005', 'Employee Wellness', 'Wellness programs, gym reimbursements, and EAP info', 'a1b2c3d4-0001-4000-8000-000000000001', '2025-01-19 08:00:00+00', '2025-01-19 08:00:00+00')
ON CONFLICT (id) DO NOTHING;

-- ===== DOCUMENTS (7 rows) =====
INSERT INTO documents (id, collection_id, filename, file_type, status, uploaded_by, uploaded_at, updated_at, error_message) VALUES
    ('c1b2c3d4-0001-4000-8000-000000000001', 'b1b2c3d4-0001-4000-8000-000000000001', '2026_benefits_summary.pdf', 'application/pdf', 'ready', 'a1b2c3d4-0002-4000-8000-000000000002', '2025-01-15 10:30:00+00', '2025-01-15 10:32:00+00', NULL),
    ('c1b2c3d4-0002-4000-8000-000000000002', 'b1b2c3d4-0001-4000-8000-000000000001', 'enrollment_guide_2026.pdf', 'application/pdf', 'ready', 'a1b2c3d4-0002-4000-8000-000000000002', '2025-01-15 11:00:00+00', '2025-01-15 11:02:00+00', NULL),
    ('c1b2c3d4-0003-4000-8000-000000000003', 'b1b2c3d4-0002-4000-8000-000000000002', 'dental_plan_details.pdf', 'application/pdf', 'ready', 'a1b2c3d4-0005-4000-8000-000000000005', '2025-01-16 09:30:00+00', '2025-01-16 09:33:00+00', NULL),
    ('c1b2c3d4-0004-4000-8000-000000000004', 'b1b2c3d4-0002-4000-8000-000000000002', 'vision_coverage.txt', 'text/plain', 'ready', 'a1b2c3d4-0005-4000-8000-000000000005', '2025-01-16 10:00:00+00', '2025-01-16 10:01:00+00', NULL),
    ('c1b2c3d4-0005-4000-8000-000000000005', 'b1b2c3d4-0003-4000-8000-000000000003', '401k_handbook.pdf', 'application/pdf', 'processing', 'a1b2c3d4-0002-4000-8000-000000000002', '2025-01-17 15:00:00+00', '2025-01-17 15:00:00+00', NULL),
    ('c1b2c3d4-0006-4000-8000-000000000006', 'b1b2c3d4-0004-4000-8000-000000000004', 'parental_leave_policy.docx', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'waiting', 'a1b2c3d4-0005-4000-8000-000000000005', '2025-01-18 11:30:00+00', '2025-01-18 11:30:00+00', NULL),
    ('c1b2c3d4-0007-4000-8000-000000000007', 'b1b2c3d4-0005-4000-8000-000000000005', 'corrupted_file.pdf', 'application/pdf', 'failed', 'a1b2c3d4-0001-4000-8000-000000000001', '2025-01-19 09:00:00+00', '2025-01-19 09:01:00+00', 'PDF extraction failed: file is encrypted or corrupted')
ON CONFLICT (id) DO NOTHING;

-- ===== DOCUMENT_CHUNKS (6 rows — for ready documents) =====
INSERT INTO document_chunks (id, document_id, chunk_index, chunk_text) VALUES
    ('d1b2c3d4-0001-4000-8000-000000000001', 'c1b2c3d4-0001-4000-8000-000000000001', 0, 'The 2026 Benefits Summary provides an overview of all employee benefit options. Medical plans include PPO Standard and PPO Premium tiers. The PPO Standard plan has a $500 individual deductible and $1,500 family deductible. The PPO Premium plan has a $250 individual deductible and $750 family deductible.'),
    ('d1b2c3d4-0002-4000-8000-000000000002', 'c1b2c3d4-0001-4000-8000-000000000001', 1, 'Open enrollment for 2026 begins on November 1, 2025 and closes on November 30, 2025. Employees who do not make an active election will be defaulted to the PPO Standard plan. Life event changes (marriage, birth, adoption) allow mid-year enrollment modifications within 30 days of the qualifying event.'),
    ('d1b2c3d4-0003-4000-8000-000000000003', 'c1b2c3d4-0002-4000-8000-000000000002', 0, 'The 2026 Enrollment Guide walks employees through the step-by-step enrollment process. Step 1: Log in to the benefits portal at benefits.company.com. Step 2: Review your current elections. Step 3: Compare available plans using the interactive plan comparison tool.'),
    ('d1b2c3d4-0004-4000-8000-000000000004', 'c1b2c3d4-0002-4000-8000-000000000002', 1, 'Dependent verification is required for any new dependents added during open enrollment. Acceptable documents include birth certificates, marriage certificates, or adoption decrees. Documents must be uploaded within 14 days of enrollment submission.'),
    ('d1b2c3d4-0005-4000-8000-000000000005', 'c1b2c3d4-0003-4000-8000-000000000003', 0, 'The Delta Dental PPO plan covers preventive care at 100% (cleanings, exams, X-rays), basic services at 80% (fillings, extractions), and major services at 50% (crowns, bridges). Annual maximum benefit per individual is $2,000. Orthodontia coverage is available for dependents under age 19 with a $1,500 lifetime max.'),
    ('d1b2c3d4-0006-4000-8000-000000000006', 'c1b2c3d4-0004-4000-8000-000000000004', 0, 'VSP Vision coverage includes one routine eye exam per year with a $10 copay. Frames allowance is $200 every 24 months. Contact lens allowance is $150 annually in lieu of frames. Laser eye surgery discount of 15% is available through participating providers.')
ON CONFLICT (id) DO NOTHING;

-- ===== FAQ_TOPICS (5 rows) =====
INSERT INTO faq_topics (id, label, created_by, created_at, updated_at) VALUES
    ('e1b2c3d4-0001-4000-8000-000000000001', 'Enrollment', 'a1b2c3d4-0002-4000-8000-000000000002', '2025-01-15 12:00:00+00', '2025-01-15 12:00:00+00'),
    ('e1b2c3d4-0002-4000-8000-000000000002', 'Dental', 'a1b2c3d4-0002-4000-8000-000000000002', '2025-01-15 12:05:00+00', '2025-01-15 12:05:00+00'),
    ('e1b2c3d4-0003-4000-8000-000000000003', 'Vision', 'a1b2c3d4-0005-4000-8000-000000000005', '2025-01-16 10:30:00+00', '2025-01-16 10:30:00+00'),
    ('e1b2c3d4-0004-4000-8000-000000000004', 'Retirement', 'a1b2c3d4-0005-4000-8000-000000000005', '2025-01-17 14:30:00+00', '2025-01-17 14:30:00+00'),
    ('e1b2c3d4-0005-4000-8000-000000000005', 'Parental Leave', 'a1b2c3d4-0001-4000-8000-000000000001', '2025-01-18 11:15:00+00', '2025-01-18 11:15:00+00')
ON CONFLICT (id) DO NOTHING;

-- ===== AUDIT_EVENTS (8 rows) =====
INSERT INTO audit_events (id, user_id, role_at_time, action_type, resource_type, resource_id, resource_name, outcome, question_excerpt, timestamp) VALUES
    ('f1b2c3d4-0001-4000-8000-000000000001', 'a1b2c3d4-0002-4000-8000-000000000002', 'contributor', 'upload', 'document', 'c1b2c3d4-0001-4000-8000-000000000001', '2026_benefits_summary.pdf', 'success', NULL, '2025-01-15 10:30:00+00'),
    ('f1b2c3d4-0002-4000-8000-000000000002', 'a1b2c3d4-0002-4000-8000-000000000002', 'contributor', 'upload', 'document', 'c1b2c3d4-0002-4000-8000-000000000002', 'enrollment_guide_2026.pdf', 'success', NULL, '2025-01-15 11:00:00+00'),
    ('f1b2c3d4-0003-4000-8000-000000000003', 'a1b2c3d4-0005-4000-8000-000000000005', 'contributor', 'upload', 'document', 'c1b2c3d4-0003-4000-8000-000000000003', 'dental_plan_details.pdf', 'success', NULL, '2025-01-16 09:30:00+00'),
    ('f1b2c3d4-0004-4000-8000-000000000004', 'a1b2c3d4-0003-4000-8000-000000000003', 'employee', 'qa_query', 'collection', 'b1b2c3d4-0001-4000-8000-000000000001', '2026 Benefits Demo', 'cited_answer', 'What is the deductible for the PPO Standard plan?', '2025-01-20 14:00:00+00'),
    ('f1b2c3d4-0005-4000-8000-000000000005', 'a1b2c3d4-0003-4000-8000-000000000003', 'employee', 'qa_query', 'collection', 'b1b2c3d4-0001-4000-8000-000000000001', '2026 Benefits Demo', 'cited_answer', 'When does open enrollment start?', '2025-01-20 14:15:00+00'),
    ('f1b2c3d4-0006-4000-8000-000000000006', 'a1b2c3d4-0004-4000-8000-000000000004', 'employee', 'qa_query', 'collection', 'b1b2c3d4-0002-4000-8000-000000000002', 'Dental & Vision Plans', 'cited_answer', 'What is the annual max for dental?', '2025-01-21 09:00:00+00'),
    ('f1b2c3d4-0007-4000-8000-000000000007', 'a1b2c3d4-0004-4000-8000-000000000004', 'employee', 'qa_query', 'collection', 'b1b2c3d4-0003-4000-8000-000000000003', 'Retirement & 401k', 'not_found', 'What is the company match percentage for 401k?', '2025-01-21 10:30:00+00'),
    ('f1b2c3d4-0008-4000-8000-000000000008', 'a1b2c3d4-0001-4000-8000-000000000001', 'admin', 'upload', 'document', 'c1b2c3d4-0007-4000-8000-000000000007', 'corrupted_file.pdf', 'failed', NULL, '2025-01-19 09:00:00+00')
ON CONFLICT (id) DO NOTHING;
