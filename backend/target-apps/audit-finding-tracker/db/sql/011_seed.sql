-- 011_seed.sql: Development seed data
-- Creates test fixtures per design §6.2: 3 users, 2 audits, 12 findings with evidence and history

-- Insert users (5-10 rows per Context seedMinRows/seedMaxRows)
INSERT INTO users (id, cognito_sub, email, role, created_at) VALUES 
    ('550e8400-e29b-41d4-a716-446655440001', 'cognito-auditor-001', 'priya.sharma@company.com', 'auditor', '2024-01-15 09:00:00+00'),
    ('550e8400-e29b-41d4-a716-446655440002', 'cognito-assignee-001', 'mike.chen@company.com', 'assignee', '2024-01-15 10:30:00+00'),
    ('550e8400-e29b-41d4-a716-446655440003', 'cognito-executive-001', 'sarah.johnson@company.com', 'executive', '2024-01-15 11:00:00+00'),
    ('550e8400-e29b-41d4-a716-446655440004', 'cognito-assignee-002', 'david.martinez@company.com', 'assignee', '2024-01-16 08:15:00+00'),
    ('550e8400-e29b-41d4-a716-446655440005', 'cognito-auditor-002', 'lisa.wang@company.com', 'auditor', '2024-01-16 09:45:00+00'),
    ('550e8400-e29b-41d4-a716-446655440006', 'cognito-assignee-003', 'james.brown@company.com', 'assignee', '2024-01-17 07:30:00+00'),
    ('550e8400-e29b-41d4-a716-446655440007', 'cognito-executive-002', 'anna.taylor@company.com', 'executive', '2024-01-17 10:00:00+00')
ON CONFLICT (cognito_sub) DO NOTHING;

-- Insert audits (5-10 rows)
INSERT INTO audits (id, title, description, status, created_by, created_at, version) VALUES 
    ('660e8400-e29b-41d4-a716-446655440001', 'Q4 2024 SOC Compliance Audit', 'Annual SOC compliance review covering access controls and data security', 'active', '550e8400-e29b-41d4-a716-446655440001', '2024-01-15 09:30:00+00', 1),
    ('660e8400-e29b-41d4-a716-446655440002', 'IT General Controls Assessment', 'Review of IT infrastructure controls and change management processes', 'active', '550e8400-e29b-41d4-a716-446655440005', '2024-01-16 10:00:00+00', 1),
    ('660e8400-e29b-41d4-a716-446655440003', 'Data Privacy Impact Assessment', 'GDPR compliance review for customer data handling', 'planning', '550e8400-e29b-41d4-a716-446655440001', '2024-01-18 14:00:00+00', 1),
    ('660e8400-e29b-41d4-a716-446655440004', 'Financial Controls Review', 'Internal controls over financial reporting', 'completed', '550e8400-e29b-41d4-a716-446655440005', '2024-01-10 09:00:00+00', 2),
    ('660e8400-e29b-41d4-a716-446655440005', 'Vendor Management Audit', 'Third-party risk assessment and vendor controls', 'active', '550e8400-e29b-41d4-a716-446655440001', '2024-01-17 11:30:00+00', 1),
    ('660e8400-e29b-41d4-a716-446655440006', 'Security Incident Response', 'Review of incident response procedures and controls', 'planning', '550e8400-e29b-41d4-a716-446655440005', '2024-01-19 08:45:00+00', 1)
ON CONFLICT (id) DO NOTHING;

-- Insert findings across all statuses (5-10 rows per Context)
INSERT INTO findings (id, audit_id, title, description, severity, status, assigned_to, due_date, created_by, created_at, version) VALUES 
    ('770e8400-e29b-41d4-a716-446655440001', '660e8400-e29b-41d4-a716-446655440001', 'Privileged Access Review Missing', 'Admin access not reviewed quarterly per SOC requirements', 'high', 'assigned', '550e8400-e29b-41d4-a716-446655440002', '2024-02-15', '550e8400-e29b-41d4-a716-446655440001', '2024-01-15 10:00:00+00', 1),
    ('770e8400-e29b-41d4-a716-446655440002', '660e8400-e29b-41d4-a716-446655440001', 'Password Policy Non-Compliance', 'Password complexity requirements not enforced system-wide', 'medium', 'in_progress', '550e8400-e29b-41d4-a716-446655440002', '2024-02-28', '550e8400-e29b-41d4-a716-446655440001', '2024-01-15 10:15:00+00', 2),
    ('770e8400-e29b-41d4-a716-446655440003', '660e8400-e29b-41d4-a716-446655440002', 'Change Management Documentation', 'IT changes lack proper approval documentation', 'critical', 'pending_verification', '550e8400-e29b-41d4-a716-446655440004', '2024-02-01', '550e8400-e29b-41d4-a716-446655440005', '2024-01-16 11:00:00+00', 1),
    ('770e8400-e29b-41d4-a716-446655440004', '660e8400-e29b-41d4-a716-446655440002', 'Database Access Controls', 'Production database access not properly segregated', 'high', 'verified', '550e8400-e29b-41d4-a716-446655440006', '2024-01-30', '550e8400-e29b-41d4-a716-446655440005', '2024-01-16 11:30:00+00', 3),
    ('770e8400-e29b-41d4-a716-446655440005', '660e8400-e29b-41d4-a716-446655440003', 'Data Retention Policy Gap', 'Customer data retention periods exceed legal requirements', 'medium', 'draft', NULL, '2024-03-15', '550e8400-e29b-41d4-a716-446655440001', '2024-01-18 14:30:00+00', 1),
    ('770e8400-e29b-41d4-a716-446655440006', '660e8400-e29b-41d4-a716-446655440005', 'Vendor Risk Assessment Missing', 'High-risk vendors lack current security assessments', 'high', 'assigned', '550e8400-e29b-41d4-a716-446655440004', '2024-02-10', '550e8400-e29b-41d4-a716-446655440001', '2024-01-17 12:00:00+00', 1),
    ('770e8400-e29b-41d4-a716-446655440007', '660e8400-e29b-41d4-a716-446655440004', 'Expense Approval Controls', 'Expense approvals bypass documented thresholds', 'low', 'closed', '550e8400-e29b-41d4-a716-446655440002', '2024-01-25', '550e8400-e29b-41d4-a716-446655440005', '2024-01-10 10:00:00+00', 4)
ON CONFLICT (id) DO NOTHING;

-- Insert evidence files (5-10 rows)
INSERT INTO evidence_files (id, finding_id, filename, s3_key, file_size, mime_type, uploaded_by, uploaded_at) VALUES 
    ('880e8400-e29b-41d4-a716-446655440001', '770e8400-e29b-41d4-a716-446655440002', 'password_policy_config.pdf', 'evidence/770e8400-e29b-41d4-a716-446655440002/password_policy_config.pdf', 245760, 'application/pdf', '550e8400-e29b-41d4-a716-446655440002', '2024-01-20 14:30:00+00'),
    ('880e8400-e29b-41d4-a716-446655440002', '770e8400-e29b-41d4-a716-446655440003', 'change_approval_process.docx', 'evidence/770e8400-e29b-41d4-a716-446655440003/change_approval_process.docx', 156832, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', '550e8400-e29b-41d4-a716-446655440004', '2024-01-25 16:00:00+00'),
    ('880e8400-e29b-41d4-a716-446655440003', '770e8400-e29b-41d4-a716-446655440004', 'db_access_matrix.xlsx', 'evidence/770e8400-e29b-41d4-a716-446655440004/db_access_matrix.xlsx', 89344, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', '550e8400-e29b-41d4-a716-446655440006', '2024-01-28 11:15:00+00'),
    ('880e8400-e29b-41d4-a716-446655440004', '770e8400-e29b-41d4-a716-446655440007', 'expense_approval_screenshot.png', 'evidence/770e8400-e29b-41d4-a716-446655440007/expense_approval_screenshot.png', 123456, 'image/png', '550e8400-e29b-41d4-a716-446655440002', '2024-01-22 09:45:00+00'),
    ('880e8400-e29b-41d4-a716-446655440005', '770e8400-e29b-41d4-a716-446655440006', 'vendor_assessment_report.pdf', 'evidence/770e8400-e29b-41d4-a716-446655440006/vendor_assessment_report.pdf', 512000, 'application/pdf', '550e8400-e29b-41d4-a716-446655440004', '2024-01-30 13:20:00+00')
ON CONFLICT (id) DO NOTHING;

-- Insert status history (5-10 rows)
INSERT INTO status_history (id, finding_id, from_status, to_status, changed_by, changed_at, comment) VALUES 
    ('990e8400-e29b-41d4-a716-446655440001', '770e8400-e29b-41d4-a716-446655440001', 'draft', 'assigned', '550e8400-e29b-41d4-a716-446655440001', '2024-01-15 11:00:00+00', 'Assigned to IT security team for remediation'),
    ('990e8400-e29b-41d4-a716-446655440002', '770e8400-e29b-41d4-a716-446655440002', 'draft', 'assigned', '550e8400-e29b-41d4-a716-446655440001', '2024-01-15 11:15:00+00', 'Password policy update required'),
    ('990e8400-e29b-41d4-a716-446655440003', '770e8400-e29b-41d4-a716-446655440002', 'assigned', 'in_progress', '550e8400-e29b-41d4-a716-446655440002', '2024-01-18 09:30:00+00', 'Started policy configuration review'),
    ('990e8400-e29b-41d4-a716-446655440004', '770e8400-e29b-41d4-a716-446655440003', 'draft', 'assigned', '550e8400-e29b-41d4-a716-446655440005', '2024-01-16 12:00:00+00', 'Critical finding - immediate attention required'),
    ('990e8400-e29b-41d4-a716-446655440005', '770e8400-e29b-41d4-a716-446655440003', 'assigned', 'in_progress', '550e8400-e29b-41d4-a716-446655440004', '2024-01-20 10:15:00+00', 'Reviewing current change management procedures'),
    ('990e8400-e29b-41d4-a716-446655440006', '770e8400-e29b-41d4-a716-446655440003', 'in_progress', 'pending_verification', '550e8400-e29b-41d4-a716-446655440004', '2024-01-25 16:30:00+00', 'New process documented and implemented'),
    ('990e8400-e29b-41d4-a716-446655440007', '770e8400-e29b-41d4-a716-446655440004', 'draft', 'assigned', '550e8400-e29b-41d4-a716-446655440005', '2024-01-16 13:00:00+00', 'Database access segregation review needed'),
    ('990e8400-e29b-41d4-a716-446655440008', '770e8400-e29b-41d4-a716-446655440004', 'assigned', 'in_progress', '550e8400-e29b-41d4-a716-446655440006', '2024-01-22 08:45:00+00', 'Implementing role-based access controls')
ON CONFLICT (id) DO NOTHING;

-- Insert finding comments (5-10 rows)
INSERT INTO finding_comments (id, finding_id, author_id, content, created_at, parent_id) VALUES 
    ('aa0e8400-e29b-41d4-a716-446655440001', '770e8400-e29b-41d4-a716-446655440001', '550e8400-e29b-41d4-a716-446655440001', 'Please prioritize this finding as it affects SOC compliance timeline', '2024-01-15 11:30:00+00', NULL),
    ('aa0e8400-e29b-41d4-a716-446655440002', '770e8400-e29b-41d4-a716-446655440001', '550e8400-e29b-41d4-a716-446655440002', 'Understood. Will coordinate with security team to complete by deadline', '2024-01-16 08:00:00+00', 'aa0e8400-e29b-41d4-a716-446655440001'),
    ('aa0e8400-e29b-41d4-a716-446655440003', '770e8400-e29b-41d4-a716-446655440002', '550e8400-e29b-41d4-a716-446655440002', 'Need clarification on which systems require the new password policy', '2024-01-18 10:00:00+00', NULL),
    ('aa0e8400-e29b-41d4-a716-446655440004', '770e8400-e29b-41d4-a716-446655440002', '550e8400-e29b-41d4-a716-446655440001', 'All domain-joined systems plus the CRM and ERP applications', '2024-01-18 14:15:00+00', 'aa0e8400-e29b-41d4-a716-446655440003'),
    ('aa0e8400-e29b-41d4-a716-446655440005', '770e8400-e29b-41d4-a716-446655440003', '550e8400-e29b-41d4-a716-446655440004', 'Evidence uploaded showing new approval workflow implementation', '2024-01-25 16:45:00+00', NULL),
    ('aa0e8400-e29b-41d4-a716-446655440006', '770e8400-e29b-41d4-a716-446655440006', '550e8400-e29b-41d4-a716-446655440001', 'This is blocking other audit activities. Please expedite vendor assessments', '2024-01-17 15:00:00+00', NULL),
    ('aa0e8400-e29b-41d4-a716-446655440007', '770e8400-e29b-41d4-a716-446655440006', '550e8400-e29b-41d4-a716-446655440004', 'Working with procurement team to prioritize high-risk vendor reviews', '2024-01-18 09:30:00+00', 'aa0e8400-e29b-41d4-a716-446655440006')
ON CONFLICT (id) DO NOTHING;