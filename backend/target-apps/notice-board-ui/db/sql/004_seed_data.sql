-- Seed data for notice board application
SET search_path TO notice_board_ui;

-- Insert default categories
INSERT INTO categories (name, description, created_at) VALUES
    ('General', 'General company announcements and updates', '2024-01-01 10:00:00'),
    ('HR', 'Human Resources announcements and policy updates', '2024-01-01 10:00:00'),
    ('IT', 'Information Technology updates and maintenance notices', '2024-01-01 10:00:00'),
    ('Events', 'Company events, meetings, and social activities', '2024-01-01 10:00:00'),
    ('Finance', 'Financial updates, budget information, and expense policies', '2024-01-01 10:00:00')
ON CONFLICT (name) DO NOTHING;

-- Insert sample notices with mix of active and archived
INSERT INTO notices (title, body, category_id, author_display_name, start_date, end_date, archived, created_at, updated_at) VALUES
    ('Welcome to the New Notice Board', 'We are excited to launch our new company notice board system. All important announcements will now be posted here for easy access and reference.', 1, 'Morgan Communications', '2024-01-01', '2024-12-31', false, '2024-01-01 10:30:00', '2024-01-01 10:30:00'),
    ('Updated Remote Work Policy', 'Effective February 1st, our remote work policy has been updated to include new guidelines for hybrid schedules. Please review the full policy document in the employee handbook.', 2, 'Sarah HR Manager', '2024-02-01', '2024-03-31', false, '2024-01-15 14:00:00', '2024-01-15 14:00:00'),
    ('Scheduled System Maintenance', 'Our email servers will undergo maintenance this Saturday from 2 AM to 6 AM. Expect intermittent outages during this window.', 3, 'Tech Support Team', '2024-01-20', '2024-01-22', false, '2024-01-18 09:15:00', '2024-01-18 09:15:00'),
    ('Annual Company Picnic Save the Date', 'Mark your calendars! Our annual company picnic is scheduled for June 15th at Riverside Park. More details to follow including RSVP information.', 4, 'Events Committee', '2024-01-10', '2024-06-20', false, '2024-01-10 11:00:00', '2024-01-10 11:00:00'),
    ('Q4 Budget Review Meeting', 'Department heads are invited to the quarterly budget review meeting on January 30th at 2 PM in Conference Room A.', 5, 'Finance Team', '2024-01-25', '2024-01-31', false, '2024-01-20 16:30:00', '2024-01-20 16:30:00'),
    ('Old Holiday Schedule - ARCHIVED', 'This notice contains the holiday schedule from last year and has been archived for reference purposes only.', 2, 'Former HR Lead', '2023-01-01', '2023-12-31', true, '2023-01-05 12:00:00', '2024-01-01 09:00:00'),
    ('Coffee Machine Replacement', 'The coffee machine on the second floor has been replaced with a new model. Please see the quick start guide posted next to the machine.', 1, 'Office Manager', '2024-01-22', NULL, false, '2024-01-22 08:45:00', '2024-01-22 08:45:00'),
    ('Security Badge Update Required', 'All employees must update their security badges at the front desk by February 15th. This is mandatory for building access.', 3, 'Security Administrator', '2024-01-15', '2024-02-20', false, '2024-01-15 13:20:00', '2024-01-15 13:20:00')
ON CONFLICT DO NOTHING;

-- Insert sample audit log entries
INSERT INTO audit_log (table_name, operation, record_id, organizer_action, created_at) VALUES
    ('categories', 'CREATE', 1, true, '2024-01-01 10:00:00'),
    ('categories', 'CREATE', 2, true, '2024-01-01 10:00:00'),
    ('notices', 'CREATE', 1, true, '2024-01-01 10:30:00'),
    ('notices', 'CREATE', 2, true, '2024-01-15 14:00:00'),
    ('notices', 'ARCHIVE', 6, true, '2024-01-01 09:00:00'),
    ('notices', 'UPDATE', 2, true, '2024-01-16 10:00:00')
ON CONFLICT DO NOTHING;