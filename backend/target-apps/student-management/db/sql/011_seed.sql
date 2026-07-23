-- 011_seed.sql
-- Dev/test seed data for students table (FR-9 fixed records + additional rows)
-- Provides 7 sample student records for development and testing

INSERT INTO students (student_id, full_name, email, course, enrollment_date, status, is_active)
VALUES
    ('STU-001', 'Alice Nguyen', 'alice@example.com', 'Computer Science', '2024-01-15', 'active', TRUE),
    ('STU-002', 'Ben Carter', 'ben@example.com', 'Data Engineering', '2024-03-01', 'active', TRUE),
    ('STU-003', 'Cleo Marsh', 'cleo@example.com', 'Cybersecurity', '2023-09-10', 'inactive', FALSE),
    ('STU-004', 'Diana Patel', 'diana@example.com', 'Computer Science', '2024-02-20', 'active', TRUE),
    ('STU-005', 'Evan Brooks', 'evan@example.com', 'Data Engineering', '2023-11-05', 'active', TRUE),
    ('STU-006', 'Fiona Lee', 'fiona@example.com', 'Cybersecurity', '2024-04-12', 'active', TRUE),
    ('STU-007', 'George Kim', 'george@example.com', 'Computer Science', '2023-06-20', 'inactive', FALSE)
ON CONFLICT DO NOTHING;
