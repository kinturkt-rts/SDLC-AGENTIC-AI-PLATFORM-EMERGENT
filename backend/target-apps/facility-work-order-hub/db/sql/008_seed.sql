-- Password for all seed users: "DevPassword123!"
-- 008_seed.sql — Dev/test fixture data for Facility Work Order Hub
-- Guard: This file is for development environments only.

SET search_path TO facility_work_order_hub;

-- ============================================================
-- USERS (6 rows: 2 requesters, 2 technicians, 1 admin, 1 leadership)
-- ============================================================
INSERT INTO users (id, email, hashed_password, display_name, role, created_at) VALUES
    ('a1000000-0000-0000-0000-000000000001', 'alice.req@example.com',    '__BCRYPT_PLACEHOLDER__', 'Alice Martinez',   'requester',        now() - INTERVAL '58 days'),
    ('a1000000-0000-0000-0000-000000000002', 'bob.req@example.com',      '__BCRYPT_PLACEHOLDER__', 'Bob Chen',          'requester',        now() - INTERVAL '57 days'),
    ('a2000000-0000-0000-0000-000000000001', 'charlie.tech@example.com', '__BCRYPT_PLACEHOLDER__', 'Charlie Davis',     'technician',       now() - INTERVAL '56 days'),
    ('a2000000-0000-0000-0000-000000000002', 'diana.tech@example.com',   '__BCRYPT_PLACEHOLDER__', 'Diana Patel',       'technician',       now() - INTERVAL '55 days'),
    ('a3000000-0000-0000-0000-000000000001', 'admin@example.com',        '__BCRYPT_PLACEHOLDER__', 'Jordan Facilities', 'facilities_admin', now() - INTERVAL '60 days'),
    ('a4000000-0000-0000-0000-000000000001', 'exec@example.com',         '__BCRYPT_PLACEHOLDER__', 'Pat Leadership',    'leadership',       now() - INTERVAL '59 days')
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- SITES (5 rows — 3 active per spec, 2 additional for min 5)
-- ============================================================
INSERT INTO sites (id, site_code, name, address_line, active, created_at, updated_at) VALUES
    ('b1000000-0000-0000-0000-000000000001', 'HQ-NYC',  'NYC Headquarters',    '100 Park Avenue, New York, NY 10017',     true,  now() - INTERVAL '60 days', now() - INTERVAL '30 days'),
    ('b1000000-0000-0000-0000-000000000002', 'BR-CHI',  'Chicago Branch',      '200 Michigan Avenue, Chicago, IL 60601',  true,  now() - INTERVAL '55 days', now() - INTERVAL '20 days'),
    ('b1000000-0000-0000-0000-000000000003', 'BR-ATL',  'Atlanta Branch',      '300 Peachtree Street, Atlanta, GA 30303', true,  now() - INTERVAL '50 days', now() - INTERVAL '15 days'),
    ('b1000000-0000-0000-0000-000000000004', 'WH-DAL',  'Dallas Warehouse',    '400 Commerce Street, Dallas, TX 75201',   true,  now() - INTERVAL '45 days', now() - INTERVAL '10 days'),
    ('b1000000-0000-0000-0000-000000000005', 'BR-OLD',  'Old Denver Office',   '500 Colfax Avenue, Denver, CO 80202',     false, now() - INTERVAL '60 days', now() - INTERVAL '5 days')
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- LOCATIONS (8 rows — 2-3 per active site, meets 5-10 range)
-- ============================================================
INSERT INTO locations (id, site_id, floor, area_label, created_at) VALUES
    ('c1000000-0000-0000-0000-000000000001', 'b1000000-0000-0000-0000-000000000001', '1',  'Main Lobby',       now() - INTERVAL '58 days'),
    ('c1000000-0000-0000-0000-000000000002', 'b1000000-0000-0000-0000-000000000001', '3',  'Server Room',      now() - INTERVAL '58 days'),
    ('c1000000-0000-0000-0000-000000000003', 'b1000000-0000-0000-0000-000000000001', '5',  'Executive Suite',  now() - INTERVAL '57 days'),
    ('c1000000-0000-0000-0000-000000000004', 'b1000000-0000-0000-0000-000000000002', '1',  'Reception',        now() - INTERVAL '54 days'),
    ('c1000000-0000-0000-0000-000000000005', 'b1000000-0000-0000-0000-000000000002', '2',  'Open Office',      now() - INTERVAL '54 days'),
    ('c1000000-0000-0000-0000-000000000006', 'b1000000-0000-0000-0000-000000000003', '1',  'Conference Room A', now() - INTERVAL '49 days'),
    ('c1000000-0000-0000-0000-000000000007', 'b1000000-0000-0000-0000-000000000003', '2',  'Break Room',       now() - INTERVAL '49 days'),
    ('c1000000-0000-0000-0000-000000000008', 'b1000000-0000-0000-0000-000000000004', '1',  'Loading Dock',     now() - INTERVAL '44 days')
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- WORK ORDERS (10 rows — all statuses, 2 overdue, 1 reopened)
-- ============================================================
INSERT INTO work_orders (id, title, description, category, priority, status, requester_id, assignee_id, site_id, location_id, due_by, reopen_reason, created_at, updated_at, assigned_at, started_at, completed_at, closed_at) VALUES
    -- WO-1: submitted (fresh)
    ('d1000000-0000-0000-0000-000000000001',
     'Lobby AC not cooling', 'Main lobby temperature is consistently above 78F in the afternoon.',
     'HVAC', 'urgent', 'submitted',
     'a1000000-0000-0000-0000-000000000001', NULL,
     'b1000000-0000-0000-0000-000000000001', 'c1000000-0000-0000-0000-000000000001',
     now() - INTERVAL '1 day', NULL,
     now() - INTERVAL '3 days', now() - INTERVAL '3 days',
     NULL, NULL, NULL, NULL),

    -- WO-2: triaged
    ('d1000000-0000-0000-0000-000000000002',
     'Flickering lights in open office', 'Fluorescent tubes on the east wall flicker intermittently.',
     'electrical', 'normal', 'triaged',
     'a1000000-0000-0000-0000-000000000002', NULL,
     'b1000000-0000-0000-0000-000000000002', 'c1000000-0000-0000-0000-000000000005',
     now() + INTERVAL '5 days', NULL,
     now() - INTERVAL '10 days', now() - INTERVAL '8 days',
     NULL, NULL, NULL, NULL),

    -- WO-3: assigned (OVERDUE — due_by in the past, not closed)
    ('d1000000-0000-0000-0000-000000000003',
     'Badge reader malfunction at reception', 'Employees cannot badge into 2nd floor after 6PM.',
     'access', 'urgent', 'assigned',
     'a1000000-0000-0000-0000-000000000001', 'a2000000-0000-0000-0000-000000000001',
     'b1000000-0000-0000-0000-000000000002', 'c1000000-0000-0000-0000-000000000004',
     now() - INTERVAL '3 days', NULL,
     now() - INTERVAL '15 days', now() - INTERVAL '12 days',
     now() - INTERVAL '12 days', NULL, NULL, NULL),

    -- WO-4: in_progress (OVERDUE — due_by in the past, not closed)
    ('d1000000-0000-0000-0000-000000000004',
     'Leaking pipe in break room', 'Water pooling under sink cabinet; needs immediate attention.',
     'plumbing', 'urgent', 'in_progress',
     'a1000000-0000-0000-0000-000000000002', 'a2000000-0000-0000-0000-000000000002',
     'b1000000-0000-0000-0000-000000000003', 'c1000000-0000-0000-0000-000000000007',
     now() - INTERVAL '2 days', NULL,
     now() - INTERVAL '20 days', now() - INTERVAL '18 days',
     now() - INTERVAL '18 days', now() - INTERVAL '16 days', NULL, NULL),

    -- WO-5: completed
    ('d1000000-0000-0000-0000-000000000005',
     'Replace HVAC filter in server room', 'Quarterly filter replacement due per maintenance schedule.',
     'HVAC', 'low', 'completed',
     'a3000000-0000-0000-0000-000000000001', 'a2000000-0000-0000-0000-000000000001',
     'b1000000-0000-0000-0000-000000000001', 'c1000000-0000-0000-0000-000000000002',
     now() - INTERVAL '5 days', NULL,
     now() - INTERVAL '30 days', now() - INTERVAL '25 days',
     now() - INTERVAL '28 days', now() - INTERVAL '26 days', now() - INTERVAL '24 days', NULL),

    -- WO-6: closed (normal lifecycle)
    ('d1000000-0000-0000-0000-000000000006',
     'Install new outlet in conference room', 'Need additional power outlet near projector mount.',
     'electrical', 'normal', 'closed',
     'a1000000-0000-0000-0000-000000000001', 'a2000000-0000-0000-0000-000000000002',
     'b1000000-0000-0000-0000-000000000003', 'c1000000-0000-0000-0000-000000000006',
     now() - INTERVAL '10 days', NULL,
     now() - INTERVAL '45 days', now() - INTERVAL '5 days',
     now() - INTERVAL '43 days', now() - INTERVAL '40 days', now() - INTERVAL '38 days', now() - INTERVAL '5 days'),

    -- WO-7: in_progress after REOPEN (closed → in_progress with reopen_reason)
    ('d1000000-0000-0000-0000-000000000007',
     'Loading dock door sticking', 'Overhead door requires excessive force to open; safety hazard.',
     'general', 'urgent', 'in_progress',
     'a1000000-0000-0000-0000-000000000002', 'a2000000-0000-0000-0000-000000000001',
     'b1000000-0000-0000-0000-000000000004', 'c1000000-0000-0000-0000-000000000008',
     now() + INTERVAL '2 days',
     'Issue recurred after initial repair; door sticking again under cold temps.',
     now() - INTERVAL '35 days', now() - INTERVAL '2 days',
     now() - INTERVAL '32 days', now() - INTERVAL '2 days', NULL, NULL),

    -- WO-8: submitted (no due_by)
    ('d1000000-0000-0000-0000-000000000008',
     'Executive suite thermostat calibration', 'Temperature reported as 3 degrees off.',
     'HVAC', 'normal', 'submitted',
     'a1000000-0000-0000-0000-000000000001', NULL,
     'b1000000-0000-0000-0000-000000000001', 'c1000000-0000-0000-0000-000000000003',
     NULL, NULL,
     now() - INTERVAL '2 days', now() - INTERVAL '2 days',
     NULL, NULL, NULL, NULL),

    -- WO-9: closed (general)
    ('d1000000-0000-0000-0000-000000000009',
     'Parking lot pothole patching', 'Large pothole near entrance; vehicle damage risk.',
     'general', 'normal', 'closed',
     'a1000000-0000-0000-0000-000000000002', 'a2000000-0000-0000-0000-000000000002',
     'b1000000-0000-0000-0000-000000000001', NULL,
     now() - INTERVAL '20 days', NULL,
     now() - INTERVAL '50 days', now() - INTERVAL '10 days',
     now() - INTERVAL '48 days', now() - INTERVAL '45 days', now() - INTERVAL '42 days', now() - INTERVAL '10 days'),

    -- WO-10: assigned
    ('d1000000-0000-0000-0000-000000000010',
     'Restroom faucet dripping', 'Second floor mens room; faucet wont fully shut off.',
     'plumbing', 'low', 'assigned',
     'a1000000-0000-0000-0000-000000000001', 'a2000000-0000-0000-0000-000000000002',
     'b1000000-0000-0000-0000-000000000002', 'c1000000-0000-0000-0000-000000000005',
     now() + INTERVAL '7 days', NULL,
     now() - INTERVAL '5 days', now() - INTERVAL '3 days',
     now() - INTERVAL '3 days', NULL, NULL, NULL)
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- WORK ORDER STATUS HISTORY (10 rows — audit entries)
-- ============================================================
INSERT INTO work_order_status_history (id, work_order_id, from_status, to_status, changed_by_user_id, changed_at, reason) VALUES
    ('e1000000-0000-0000-0000-000000000001', 'd1000000-0000-0000-0000-000000000002', 'submitted', 'triaged', 'a3000000-0000-0000-0000-000000000001', now() - INTERVAL '8 days', NULL),
    ('e1000000-0000-0000-0000-000000000002', 'd1000000-0000-0000-0000-000000000003', 'submitted', 'triaged', 'a3000000-0000-0000-0000-000000000001', now() - INTERVAL '13 days', NULL),
    ('e1000000-0000-0000-0000-000000000003', 'd1000000-0000-0000-0000-000000000003', 'triaged', 'assigned', 'a3000000-0000-0000-0000-000000000001', now() - INTERVAL '12 days', NULL),
    ('e1000000-0000-0000-0000-000000000004', 'd1000000-0000-0000-0000-000000000004', 'submitted', 'triaged', 'a3000000-0000-0000-0000-000000000001', now() - INTERVAL '19 days', NULL),
    ('e1000000-0000-0000-0000-000000000005', 'd1000000-0000-0000-0000-000000000004', 'triaged', 'assigned', 'a3000000-0000-0000-0000-000000000001', now() - INTERVAL '18 days', NULL),
    ('e1000000-0000-0000-0000-000000000006', 'd1000000-0000-0000-0000-000000000004', 'assigned', 'in_progress', 'a2000000-0000-0000-0000-000000000002', now() - INTERVAL '16 days', NULL),
    ('e1000000-0000-0000-0000-000000000007', 'd1000000-0000-0000-0000-000000000006', 'completed', 'closed', 'a3000000-0000-0000-0000-000000000001', now() - INTERVAL '5 days', NULL),
    ('e1000000-0000-0000-0000-000000000008', 'd1000000-0000-0000-0000-000000000007', 'closed', 'in_progress', 'a3000000-0000-0000-0000-000000000001', now() - INTERVAL '2 days', 'Issue recurred after initial repair; door sticking again under cold temps.'),
    ('e1000000-0000-0000-0000-000000000009', 'd1000000-0000-0000-0000-000000000009', 'completed', 'closed', 'a3000000-0000-0000-0000-000000000001', now() - INTERVAL '10 days', NULL),
    ('e1000000-0000-0000-0000-000000000010', 'd1000000-0000-0000-0000-000000000010', 'triaged', 'assigned', 'a3000000-0000-0000-0000-000000000001', now() - INTERVAL '3 days', NULL)
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- COMMENTS (8 rows — on at least 4 orders)
-- ============================================================
INSERT INTO comments (id, work_order_id, author_id, body, created_at) VALUES
    ('f1000000-0000-0000-0000-000000000001', 'd1000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000001', 'Temperature hit 82F today at 2pm. Getting complaints from reception staff.', now() - INTERVAL '2 days'),
    ('f1000000-0000-0000-0000-000000000002', 'd1000000-0000-0000-0000-000000000003', 'a2000000-0000-0000-0000-000000000001', 'Inspected the badge reader — firmware update required. Parts ordered.', now() - INTERVAL '10 days'),
    ('f1000000-0000-0000-0000-000000000003', 'd1000000-0000-0000-0000-000000000003', 'a3000000-0000-0000-0000-000000000001', 'Escalating priority due to security concern. Please expedite.', now() - INTERVAL '9 days'),
    ('f1000000-0000-0000-0000-000000000004', 'd1000000-0000-0000-0000-000000000004', 'a2000000-0000-0000-0000-000000000002', 'Shut off water supply to affected pipe. Permanent fix tomorrow.', now() - INTERVAL '15 days'),
    ('f1000000-0000-0000-0000-000000000005', 'd1000000-0000-0000-0000-000000000005', 'a2000000-0000-0000-0000-000000000001', 'Filter replaced. Airflow measured at spec.', now() - INTERVAL '25 days'),
    ('f1000000-0000-0000-0000-000000000006', 'd1000000-0000-0000-0000-000000000006', 'a2000000-0000-0000-0000-000000000002', 'Outlet installed and tested with projector.', now() - INTERVAL '38 days'),
    ('f1000000-0000-0000-0000-000000000007', 'd1000000-0000-0000-0000-000000000007', 'a2000000-0000-0000-0000-000000000001', 'Investigating root cause of recurrence. May need full track replacement.', now() - INTERVAL '1 day'),
    ('f1000000-0000-0000-0000-000000000008', 'd1000000-0000-0000-0000-000000000009', 'a3000000-0000-0000-0000-000000000001', 'Vendor confirmed repair. Closing out.', now() - INTERVAL '10 days')
ON CONFLICT (id) DO NOTHING;
