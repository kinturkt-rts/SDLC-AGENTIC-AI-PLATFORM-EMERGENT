-- Password for all seed users: "PolicyPortal2024!"

SET search_path TO jwt_rag_streamlit, public;

-- Insert test users with different roles
INSERT INTO jwt_rag_streamlit.users (id, email, password_hash, role, status, created_at) VALUES
    (1, 'admin@company.com', '__BCRYPT_PLACEHOLDER__', 'admin', 'active', '2024-01-15 09:00:00+00'),
    (2, 'hr.manager@company.com', '__BCRYPT_PLACEHOLDER__', 'contributor', 'active', '2024-01-16 10:30:00+00'),
    (3, 'it.support@company.com', '__BCRYPT_PLACEHOLDER__', 'contributor', 'active', '2024-01-17 11:15:00+00'),
    (4, 'jane.employee@company.com', '__BCRYPT_PLACEHOLDER__', 'viewer', 'active', '2024-01-18 14:20:00+00'),
    (5, 'john.contractor@company.com', '__BCRYPT_PLACEHOLDER__', 'viewer', 'active', '2024-01-19 08:45:00+00'),
    (6, 'sarah.manager@company.com', '__BCRYPT_PLACEHOLDER__', 'contributor', 'active', '2024-01-20 12:10:00+00'),
    (7, 'mike.analyst@company.com', '__BCRYPT_PLACEHOLDER__', 'viewer', 'active', '2024-01-21 15:30:00+00'),
    (8, 'lisa.hr@company.com', '__BCRYPT_PLACEHOLDER__', 'viewer', 'inactive', '2024-01-22 09:50:00+00')
ON CONFLICT (email) DO NOTHING;

-- Reset sequence to avoid conflicts
SELECT setval('jwt_rag_streamlit.users_id_seq', (SELECT COALESCE(MAX(id), 1) FROM jwt_rag_streamlit.users));

-- Insert test collections
INSERT INTO jwt_rag_streamlit.collections (id, name, description, owner_id, archived, created_at) VALUES
    (1, 'Employee Handbook', 'Official employee policies, benefits, and procedures', 1, false, '2024-01-15 10:00:00+00'),
    (2, 'IT Security Policies', 'Information security standards and compliance requirements', 3, false, '2024-01-17 12:00:00+00'),
    (3, 'HR Procedures', 'Human resources processes and guidelines', 2, false, '2024-01-16 11:00:00+00'),
    (4, 'Expense & Travel', 'Expense reporting and travel policy documents', 2, false, '2024-01-18 13:00:00+00'),
    (5, 'Safety Guidelines', 'Workplace safety and emergency procedures', 1, false, '2024-01-19 14:00:00+00'),
    (6, 'Archived Policies', 'Outdated policies kept for reference', 1, true, '2024-01-10 09:00:00+00')
ON CONFLICT (name) DO NOTHING;

-- Reset sequence to avoid conflicts
SELECT setval('jwt_rag_streamlit.collections_id_seq', (SELECT COALESCE(MAX(id), 1) FROM jwt_rag_streamlit.collections));

-- Insert collection memberships
INSERT INTO jwt_rag_streamlit.collection_memberships (collection_id, user_id, role, created_at) VALUES
    -- Employee Handbook - accessible by all
    (1, 2, 'contributor', '2024-01-16 10:30:00+00'),
    (1, 3, 'viewer', '2024-01-17 11:15:00+00'),
    (1, 4, 'viewer', '2024-01-18 14:20:00+00'),
    (1, 5, 'viewer', '2024-01-19 08:45:00+00'),
    (1, 6, 'contributor', '2024-01-20 12:10:00+00'),
    (1, 7, 'viewer', '2024-01-21 15:30:00+00'),
    -- IT Security - IT and managers only
    (2, 1, 'contributor', '2024-01-15 09:00:00+00'),
    (2, 6, 'viewer', '2024-01-20 12:10:00+00'),
    (2, 7, 'viewer', '2024-01-21 15:30:00+00'),
    -- HR Procedures - HR team and some managers
    (3, 1, 'contributor', '2024-01-15 09:00:00+00'),
    (3, 6, 'contributor', '2024-01-20 12:10:00+00'),
    (3, 8, 'viewer', '2024-01-22 09:50:00+00'),
    -- Expense & Travel - all employees
    (4, 3, 'viewer', '2024-01-17 11:15:00+00'),
    (4, 4, 'viewer', '2024-01-18 14:20:00+00'),
    (4, 5, 'viewer', '2024-01-19 08:45:00+00'),
    (4, 6, 'contributor', '2024-01-20 12:10:00+00'),
    (4, 7, 'viewer', '2024-01-21 15:30:00+00'),
    -- Safety Guidelines - managers and safety officers
    (5, 2, 'contributor', '2024-01-16 10:30:00+00'),
    (5, 3, 'contributor', '2024-01-17 11:15:00+00'),
    (5, 6, 'viewer', '2024-01-20 12:10:00+00')
ON CONFLICT (collection_id, user_id) DO NOTHING;

-- Insert sample documents
INSERT INTO jwt_rag_streamlit.documents (id, title, file_path, collection_id, status, uploaded_by, created_at) VALUES
    (1, 'Employee Handbook 2024', '/policies/employee_handbook_2024.pdf', 1, 'success', 1, '2024-01-15 11:00:00+00'),
    (2, 'Code of Conduct', '/policies/code_of_conduct.pdf', 1, 'success', 2, '2024-01-16 12:00:00+00'),
    (3, 'Password Policy', '/security/password_policy.pdf', 2, 'success', 3, '2024-01-17 13:00:00+00'),
    (4, 'Data Classification Guide', '/security/data_classification.pdf', 2, 'success', 3, '2024-01-17 14:00:00+00'),
    (5, 'Recruitment Process', '/hr/recruitment_process.pdf', 3, 'success', 2, '2024-01-18 10:00:00+00'),
    (6, 'Expense Reporting Guidelines', '/finance/expense_guidelines.pdf', 4, 'success', 2, '2024-01-18 15:00:00+00'),
    (7, 'Emergency Procedures', '/safety/emergency_procedures.pdf', 5, 'success', 1, '2024-01-19 16:00:00+00'),
    (8, 'Travel Policy Draft', '/policies/travel_policy_draft.pdf', 4, 'processing', 6, '2024-01-22 10:00:00+00')
ON CONFLICT DO NOTHING;

-- Reset sequence to avoid conflicts
SELECT setval('jwt_rag_streamlit.documents_id_seq', (SELECT COALESCE(MAX(id), 1) FROM jwt_rag_streamlit.documents));

-- Insert sample document chunks with mock embeddings (will be replaced with real embeddings during ingestion)
INSERT INTO jwt_rag_streamlit.document_chunks (id, document_id, content, embedding, page_number, chunk_index, created_at) VALUES
    (1, 1, 'Welcome to our company! This handbook contains important information about our policies, procedures, and benefits. Please read it carefully and keep it for reference.', NULL, 1, 0, '2024-01-15 11:30:00+00'),
    (2, 1, 'Our vacation policy allows for 15 days of paid time off for new employees, increasing to 20 days after two years of service. Vacation requests must be submitted at least two weeks in advance.', NULL, 5, 1, '2024-01-15 11:30:00+00'),
    (3, 2, 'All employees are expected to maintain the highest standards of professional conduct. This includes treating colleagues with respect, maintaining confidentiality, and following all company policies.', NULL, 1, 0, '2024-01-16 12:30:00+00'),
    (4, 3, 'Passwords must be at least 12 characters long and include a combination of uppercase letters, lowercase letters, numbers, and special characters. Passwords should be changed every 90 days.', NULL, 2, 0, '2024-01-17 13:30:00+00'),
    (5, 4, 'Confidential data includes customer information, financial records, and proprietary business information. This data must be encrypted at rest and in transit, and access must be logged.', NULL, 3, 0, '2024-01-17 14:30:00+00'),
    (6, 5, 'Our recruitment process begins with job posting and candidate screening. All positions must be posted internally for 5 business days before external posting. Interview panels must include at least two interviewers.', NULL, 1, 0, '2024-01-18 10:30:00+00'),
    (7, 6, 'Expense reports must be submitted within 30 days of incurring the expense. Receipts are required for all expenses over $25. Meals are reimbursed up to $50 per day for business travel.', NULL, 2, 0, '2024-01-18 15:30:00+00'),
    (8, 7, 'In case of fire, evacuate immediately using the nearest exit. Do not use elevators. Proceed to the designated assembly area and wait for further instructions from emergency personnel.', NULL, 1, 0, '2024-01-19 16:30:00+00')
ON CONFLICT DO NOTHING;

-- Reset sequence to avoid conflicts
SELECT setval('jwt_rag_streamlit.document_chunks_id_seq', (SELECT COALESCE(MAX(id), 1) FROM jwt_rag_streamlit.document_chunks));

-- Insert sample chat sessions
INSERT INTO jwt_rag_streamlit.chat_sessions (id, collection_id, user_id, created_at) VALUES
    (1, 1, 4, '2024-01-20 09:00:00+00'),
    (2, 1, 5, '2024-01-20 14:00:00+00'),
    (3, 2, 7, '2024-01-21 10:00:00+00'),
    (4, 4, 4, '2024-01-21 15:00:00+00'),
    (5, 1, 7, '2024-01-22 11:00:00+00')
ON CONFLICT DO NOTHING;

-- Reset sequence to avoid conflicts
SELECT setval('jwt_rag_streamlit.chat_sessions_id_seq', (SELECT COALESCE(MAX(id), 1) FROM jwt_rag_streamlit.chat_sessions));

-- Insert sample chat messages
INSERT INTO jwt_rag_streamlit.chat_messages (session_id, content, is_user, confidence_score, citations, created_at) VALUES
    (1, 'How many vacation days do I get as a new employee?', true, NULL, NULL, '2024-01-20 09:01:00+00'),
    (1, 'As a new employee, you are entitled to 15 days of paid time off. After two years of service, this increases to 20 days. Vacation requests must be submitted at least two weeks in advance.', false, 0.92, '{"documents": [{"title": "Employee Handbook 2024", "page": 5, "confidence": 0.92}]}', '2024-01-20 09:01:30+00'),
    (2, 'What is the code of conduct regarding respect in the workplace?', true, NULL, NULL, '2024-01-20 14:01:00+00'),
    (2, 'All employees are expected to maintain the highest standards of professional conduct, which includes treating colleagues with respect, maintaining confidentiality, and following all company policies.', false, 0.89, '{"documents": [{"title": "Code of Conduct", "page": 1, "confidence": 0.89}]}', '2024-01-20 14:01:25+00'),
    (3, 'What are the password requirements?', true, NULL, NULL, '2024-01-21 10:01:00+00'),
    (3, 'Passwords must be at least 12 characters long and include a combination of uppercase letters, lowercase letters, numbers, and special characters. Passwords should be changed every 90 days.', false, 0.95, '{"documents": [{"title": "Password Policy", "page": 2, "confidence": 0.95}]}', '2024-01-21 10:01:20+00'),
    (4, 'What is the daily meal allowance for business travel?', true, NULL, NULL, '2024-01-21 15:01:00+00'),
    (4, 'Meals are reimbursed up to $50 per day for business travel. Receipts are required for all expenses over $25, and expense reports must be submitted within 30 days.', false, 0.87, '{"documents": [{"title": "Expense Reporting Guidelines", "page": 2, "confidence": 0.87}]}', '2024-01-21 15:01:35+00'),
    (5, 'Tell me about the recruitment process timeline', true, NULL, NULL, '2024-01-22 11:01:00+00'),
    (5, 'Our recruitment process begins with job posting and candidate screening. All positions must be posted internally for 5 business days before external posting. Interview panels must include at least two interviewers.', false, 0.91, '{"documents": [{"title": "Recruitment Process", "page": 1, "confidence": 0.91}]}', '2024-01-22 11:01:40+00')
ON CONFLICT DO NOTHING;

-- Insert sample audit log entries
INSERT INTO jwt_rag_streamlit.audit_log (user_id, action, resource_type, resource_id, details, ip_address, created_at) VALUES
    (1, 'user_login', NULL, NULL, '{"email": "admin@company.com", "success": true}', '192.168.1.100', '2024-01-15 08:55:00+00'),
    (1, 'document_upload', 'document', 1, '{"filename": "employee_handbook_2024.pdf", "collection": "Employee Handbook"}', '192.168.1.100', '2024-01-15 11:00:00+00'),
    (2, 'user_login', NULL, NULL, '{"email": "hr.manager@company.com", "success": true}', '192.168.1.101', '2024-01-16 10:25:00+00'),
    (2, 'document_upload', 'document', 2, '{"filename": "code_of_conduct.pdf", "collection": "Employee Handbook"}', '192.168.1.101', '2024-01-16 12:00:00+00'),
    (4, 'user_login', NULL, NULL, '{"email": "jane.employee@company.com", "success": true}', '192.168.1.102', '2024-01-18 14:15:00+00'),
    (4, 'chat_query', 'collection', 1, '{"query": "vacation days", "collection": "Employee Handbook", "confidence": 0.92}', '192.168.1.102', '2024-01-20 09:01:00+00'),
    (3, 'user_login', NULL, NULL, '{"email": "it.support@company.com", "success": true}', '192.168.1.103', '2024-01-17 11:10:00+00'),
    (7, 'chat_query', 'collection', 2, '{"query": "password requirements", "collection": "IT Security Policies", "confidence": 0.95}', '192.168.1.104', '2024-01-21 10:01:00+00'),
    (6, 'collection_create', 'collection', 4, '{"name": "Expense & Travel", "description": "Expense reporting and travel policy documents"}', '192.168.1.105', '2024-01-18 13:00:00+00'),
    (5, 'user_login', NULL, NULL, '{"email": "john.contractor@company.com", "success": false, "reason": "invalid_password"}', '192.168.1.106', '2024-01-19 08:40:00+00')
ON CONFLICT DO NOTHING;