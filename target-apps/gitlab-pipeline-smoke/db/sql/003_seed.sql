-- 003_seed.sql
-- Dev seed data for gitlab-pipeline-smoke

SET search_path TO gitlab_pipeline_smoke, public;

-- Insert categories (3 as specified in design §6.2)
INSERT INTO gitlab_pipeline_smoke.categories (id, name, description, created_at) VALUES
    ('550e8400-e29b-41d4-a716-446655440000', 'General', 'General announcements and company-wide notices', '2024-01-01 10:00:00+00'),
    ('550e8400-e29b-41d4-a716-446655440001', 'HR', 'Human resources updates, benefits, and policy changes', '2024-01-01 10:00:00+00'),
    ('550e8400-e29b-41d4-a716-446655440002', 'Engineering', 'Technical updates, deployment notices, and engineering wins', '2024-01-01 10:00:00+00')
ON CONFLICT (name) DO NOTHING;

-- Insert notices (8 sample notices with mixed states as specified)
INSERT INTO gitlab_pipeline_smoke.notices (
    id, category_id, title, body, author_name, starts_at, ends_at, is_archived, created_at, updated_at
) VALUES
    -- Active notice
    ('660e8400-e29b-41d4-a716-446655440000', 
     '550e8400-e29b-41d4-a716-446655440000', 
     'Welcome to Q1 2024', 
     'We are starting the new quarter with exciting initiatives. Please review the updated project roadmaps and team goals in the shared drive.',
     'Alice Johnson',
     '2024-01-01 09:00:00+00',
     '2024-12-31 23:59:59+00',
     false,
     '2024-01-01 09:00:00+00',
     '2024-01-01 09:00:00+00'),
    
    -- Active HR notice
    ('660e8400-e29b-41d4-a716-446655440001',
     '550e8400-e29b-41d4-a716-446655440001',
     'New Health Insurance Options',
     'Open enrollment for health insurance is now available. Please log into the benefits portal by January 31st to make your selections. Contact HR with any questions.',
     'Bob Smith',
     '2024-01-15 08:00:00+00',
     '2024-01-31 17:00:00+00',
     false,
     '2024-01-15 08:00:00+00',
     '2024-01-15 08:00:00+00'),
    
    -- Active engineering notice
    ('660e8400-e29b-41d4-a716-446655440002',
     '550e8400-e29b-41d4-a716-446655440002',
     'Database Migration Scheduled',
     'The user authentication database will undergo scheduled maintenance this Saturday from 2-4 AM EST. All services should remain available during this window.',
     'Carol Davis',
     '2024-01-20 07:00:00+00',
     '2024-02-01 06:00:00+00',
     false,
     '2024-01-20 07:00:00+00',
     '2024-01-20 07:00:00+00'),
    
    -- Future notice (starts_at > now)
    ('660e8400-e29b-41d4-a716-446655440003',
     '550e8400-e29b-41d4-a716-446655440000',
     'Upcoming All-Hands Meeting',
     'Our quarterly all-hands meeting is scheduled for next month. We will cover company performance, new product launches, and team recognitions.',
     'David Wilson',
     '2024-06-01 14:00:00+00',
     '2024-06-01 16:00:00+00',
     false,
     '2024-01-25 10:00:00+00',
     '2024-01-25 10:00:00+00'),
    
    -- Expired notice (ends_at < now)
    ('660e8400-e29b-41d4-a716-446655440004',
     '550e8400-e29b-41d4-a716-446655440001',
     'Holiday Party RSVP Reminder',
     'Please RSVP for the holiday party by December 15th. We need an accurate headcount for catering. The party will be held at the downtown office.',
     'Eva Martinez',
     '2023-12-01 09:00:00+00',
     '2023-12-15 17:00:00+00',
     false,
     '2023-12-01 09:00:00+00',
     '2023-12-01 09:00:00+00'),
    
    -- Archived notice
    ('660e8400-e29b-41d4-a716-446655440005',
     '550e8400-e29b-41d4-a716-446655440002',
     'Legacy System Deprecation',
     'The old ticketing system has been successfully deprecated and replaced. All data has been migrated to the new system. Training materials are available on the wiki.',
     'Frank Brown',
     '2023-11-01 08:00:00+00',
     '2024-01-31 23:59:59+00',
     true,
     '2023-11-01 08:00:00+00',
     '2023-12-15 10:30:00+00'),
    
    -- Another active notice
    ('660e8400-e29b-41d4-a716-446655440006',
     '550e8400-e29b-41d4-a716-446655440002',
     'Code Review Guidelines Updated',
     'We have updated our code review guidelines to improve code quality and team collaboration. Please review the new documentation in the engineering wiki.',
     'Grace Lee',
     '2024-01-18 09:30:00+00',
     '2024-03-01 23:59:59+00',
     false,
     '2024-01-18 09:30:00+00',
     '2024-01-18 09:30:00+00'),
    
    -- Additional active notice to meet seedMinRows requirement
    ('660e8400-e29b-41d4-a716-446655440007',
     '550e8400-e29b-41d4-a716-446655440000',
     'Security Training Mandatory',
     'All employees must complete the annual security awareness training by February 15th. Links to the training modules have been sent to your company email.',
     'Henry Taylor',
     '2024-01-22 08:00:00+00',
     '2024-02-15 23:59:59+00',
     false,
     '2024-01-22 08:00:00+00',
     '2024-01-22 08:00:00+00')
ON CONFLICT (id) DO NOTHING;