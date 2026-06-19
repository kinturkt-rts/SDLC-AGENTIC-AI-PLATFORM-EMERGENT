-- Development seed data for library-catalog
-- Provides 10 books, 5 members, 7 loans, 3 holds, and 8 audit entries for testing

-- Books: 10 sample tech/business titles
INSERT INTO books (id, isbn, title, author, total_copies) VALUES
    ('550e8400-e29b-41d4-a716-446655440001', '9780134685991', 'Effective Java', 'Joshua Bloch', 3),
    ('550e8400-e29b-41d4-a716-446655440002', '9780135957059', 'The Pragmatic Programmer', 'David Thomas', 2),
    ('550e8400-e29b-41d4-a716-446655440003', '9781617295287', 'Spring Boot in Action', 'Craig Walls', 2),
    ('550e8400-e29b-41d4-a716-446655440004', '9780596517748', 'JavaScript: The Good Parts', 'Douglas Crockford', 1),
    ('550e8400-e29b-41d4-a716-446655440005', '9780134494166', 'Clean Architecture', 'Robert C. Martin', 2),
    ('550e8400-e29b-41d4-a716-446655440006', '9781491950357', 'Building Microservices', 'Sam Newman', 1),
    ('550e8400-e29b-41d4-a716-446655440007', '9780321125217', 'Domain-Driven Design', 'Eric Evans', 1),
    ('550e8400-e29b-41d4-a716-446655440008', '9780134757599', 'Refactoring', 'Martin Fowler', 2),
    ('550e8400-e29b-41d4-a716-446655440009', '9780134052502', 'The DevOps Handbook', 'Gene Kim', 1),
    ('550e8400-e29b-41d4-a716-446655440010', '9781449373320', 'Designing Data-Intensive Applications', 'Martin Kleppmann', 1)
ON CONFLICT (id) DO NOTHING;

-- Members: 5 test employees
INSERT INTO members (id, email, member_key, name) VALUES
    ('660e8400-e29b-41d4-a716-446655440001', 'alice.developer@company.com', 'MBR_alice_dev_2024', 'Alice Developer'),
    ('660e8400-e29b-41d4-a716-446655440002', 'bob.manager@company.com', 'MBR_bob_mgr_2024', 'Bob Manager'),
    ('660e8400-e29b-41d4-a716-446655440003', 'carol.analyst@company.com', 'MBR_carol_analyst_2024', 'Carol Analyst'),
    ('660e8400-e29b-41d4-a716-446655440004', 'david.ops@company.com', 'MBR_david_ops_2024', 'David Operations'),
    ('660e8400-e29b-41d4-a716-446655440005', 'eve.architect@company.com', 'MBR_eve_arch_2024', 'Eve Architect')
ON CONFLICT (id) DO NOTHING;

-- Loans: 7 test loans (5 active, 2 returned) for testing business logic
INSERT INTO loans (id, book_id, member_id, checkout_at, due_at, returned_at) VALUES
    ('770e8400-e29b-41d4-a716-446655440001', '550e8400-e29b-41d4-a716-446655440001', '660e8400-e29b-41d4-a716-446655440001', 
     NOW() - INTERVAL '10 days', NOW() + INTERVAL '4 days', NULL),
    ('770e8400-e29b-41d4-a716-446655440002', '550e8400-e29b-41d4-a716-446655440002', '660e8400-e29b-41d4-a716-446655440002', 
     NOW() - INTERVAL '5 days', NOW() + INTERVAL '9 days', NULL),
    ('770e8400-e29b-41d4-a716-446655440003', '550e8400-e29b-41d4-a716-446655440003', '660e8400-e29b-41d4-a716-446655440003', 
     NOW() - INTERVAL '20 days', NOW() - INTERVAL '6 days', NULL), -- Overdue loan
    ('770e8400-e29b-41d4-a716-446655440004', '550e8400-e29b-41d4-a716-446655440004', '660e8400-e29b-41d4-a716-446655440004', 
     NOW() - INTERVAL '3 days', NOW() + INTERVAL '11 days', NULL),
    ('770e8400-e29b-41d4-a716-446655440005', '550e8400-e29b-41d4-a716-446655440005', '660e8400-e29b-41d4-a716-446655440005', 
     NOW() - INTERVAL '1 day', NOW() + INTERVAL '13 days', NULL),
    ('770e8400-e29b-41d4-a716-446655440006', '550e8400-e29b-41d4-a716-446655440006', '660e8400-e29b-41d4-a716-446655440001', 
     NOW() - INTERVAL '30 days', NOW() - INTERVAL '16 days', NOW() - INTERVAL '2 days'), -- Returned
    ('770e8400-e29b-41d4-a716-446655440007', '550e8400-e29b-41d4-a716-446655440007', '660e8400-e29b-41d4-a716-446655440002', 
     NOW() - INTERVAL '25 days', NOW() - INTERVAL '11 days', NOW() - INTERVAL '5 days')  -- Returned
ON CONFLICT (id) DO NOTHING;

-- Holds: 3 test holds (2 active, 1 fulfilled) for FIFO queue testing
INSERT INTO holds (id, book_id, member_id, placed_at, fulfilled_at, cancelled_at) VALUES
    ('880e8400-e29b-41d4-a716-446655440001', '550e8400-e29b-41d4-a716-446655440004', '660e8400-e29b-41d4-a716-446655440002', 
     NOW() - INTERVAL '3 days', NULL, NULL), -- Active hold (oldest)
    ('880e8400-e29b-41d4-a716-446655440002', '550e8400-e29b-41d4-a716-446655440004', '660e8400-e29b-41d4-a716-446655440003', 
     NOW() - INTERVAL '1 day', NULL, NULL),  -- Active hold (newer)
    ('880e8400-e29b-41d4-a716-446655440003', '550e8400-e29b-41d4-a716-446655440006', '660e8400-e29b-41d4-a716-446655440004', 
     NOW() - INTERVAL '5 days', NOW() - INTERVAL '2 days', NULL) -- Fulfilled hold
ON CONFLICT (id) DO NOTHING;

-- Audit log: 8 sample entries for different operations
INSERT INTO audit_log (entity_type, entity_id, action, member_id, details) VALUES
    ('books', '550e8400-e29b-41d4-a716-446655440001', 'CREATE', NULL, '{"created_by": "librarian", "isbn": "9780134685991"}'),
    ('members', '660e8400-e29b-41d4-a716-446655440001', 'CREATE', NULL, '{"created_by": "librarian", "email": "alice.developer@company.com"}'),
    ('loans', '770e8400-e29b-41d4-a716-446655440001', 'CHECKOUT', '660e8400-e29b-41d4-a716-446655440001', '{"book_title": "Effective Java"}'),
    ('loans', '770e8400-e29b-41d4-a716-446655440006', 'RETURN', '660e8400-e29b-41d4-a716-446655440001', '{"book_title": "Building Microservices", "days_borrowed": 28}'),
    ('holds', '880e8400-e29b-41d4-a716-446655440001', 'PLACE_HOLD', '660e8400-e29b-41d4-a716-446655440002', '{"book_title": "JavaScript: The Good Parts", "queue_position": 1}'),
    ('holds', '880e8400-e29b-41d4-a716-446655440003', 'FULFILL_HOLD', '660e8400-e29b-41d4-a716-446655440004', '{"book_title": "Building Microservices", "wait_days": 3}'),
    ('books', '550e8400-e29b-41d4-a716-446655440008', 'UPDATE', NULL, '{"updated_by": "librarian", "field": "total_copies", "old_value": 1, "new_value": 2}'),
    ('loans', '770e8400-e29b-41d4-a716-446655440003', 'OVERDUE_NOTICE', '660e8400-e29b-41d4-a716-446655440003', '{"book_title": "Spring Boot in Action", "days_overdue": 6}')
ON CONFLICT DO NOTHING;