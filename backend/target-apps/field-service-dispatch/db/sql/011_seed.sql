-- Password for all seed users: "FieldService2024!"
-- 011_seed.sql
-- Dev/test seed data for Field Service Dispatch
-- Covers: 5 technicians, 5 customers, 3 users, 15 work orders, assignments, parts, audit log

-- ============================================================
-- Technicians (5)
-- ============================================================
INSERT INTO technicians (id, name, skills, active, created_at) VALUES
    ('a0000001-0000-0000-0000-000000000001', 'Carlos Mendez', ARRAY['residential','commercial'], true, '2024-01-15 08:00:00+00'),
    ('a0000001-0000-0000-0000-000000000002', 'Janice Park', ARRAY['residential','install'], true, '2024-01-15 08:00:00+00'),
    ('a0000001-0000-0000-0000-000000000003', 'Tyrone Williams', ARRAY['commercial','install'], true, '2024-01-15 08:00:00+00'),
    ('a0000001-0000-0000-0000-000000000004', 'Sarah Chen', ARRAY['residential'], true, '2024-02-01 08:00:00+00'),
    ('a0000001-0000-0000-0000-000000000005', 'Derek Johnson', ARRAY['commercial','residential','install'], false, '2024-02-01 08:00:00+00')
ON CONFLICT DO NOTHING;

-- ============================================================
-- Customers (5)
-- ============================================================
INSERT INTO customers (id, full_name, phone, email, street, city, state, zip, created_at, deleted_at) VALUES
    ('b0000001-0000-0000-0000-000000000001', 'Lakewood Medical Center', '614-555-0101', 'facilities@lakewoodmed.com', '2200 Olentangy River Rd', 'Columbus', 'OH', '43210', '2024-01-20 09:00:00+00', NULL),
    ('b0000001-0000-0000-0000-000000000002', 'Maria Gonzalez', '614-555-0202', 'maria.g@email.com', '487 Maple Ave', 'Dublin', 'OH', '43017', '2024-01-22 10:30:00+00', NULL),
    ('b0000001-0000-0000-0000-000000000003', 'Sunrise Bakery', '614-555-0303', NULL, '109 High St', 'Worthington', 'OH', '43085', '2024-02-05 14:00:00+00', NULL),
    ('b0000001-0000-0000-0000-000000000004', 'James Patterson', '614-555-0404', 'jpatterson@email.com', '3321 Riverside Dr', 'Upper Arlington', 'OH', '43221', '2024-02-10 11:00:00+00', NULL),
    ('b0000001-0000-0000-0000-000000000005', 'Hilltop Community Church', '614-555-0505', 'office@hilltopcc.org', '890 Wilson Rd', 'Columbus', 'OH', '43204', '2024-02-15 08:30:00+00', NULL)
ON CONFLICT DO NOTHING;

-- ============================================================
-- Users (3: dispatcher, technician, owner)
-- ============================================================
INSERT INTO users (id, username, hashed_password, role, technician_id) VALUES
    ('c0000001-0000-0000-0000-000000000001', 'dana_dispatch', '__BCRYPT_PLACEHOLDER__', 'dispatcher', NULL),
    ('c0000001-0000-0000-0000-000000000002', 'carlos_tech', '__BCRYPT_PLACEHOLDER__', 'technician', 'a0000001-0000-0000-0000-000000000001'),
    ('c0000001-0000-0000-0000-000000000003', 'frank_owner', '__BCRYPT_PLACEHOLDER__', 'owner', NULL)
ON CONFLICT DO NOTHING;

-- ============================================================
-- Work Orders (15 across all statuses)
-- Uses CURRENT_DATE for SLA-relevant orders so breach logic works on any day
-- ============================================================
INSERT INTO work_orders (id, customer_id, description, priority, scheduled_date, time_window, status, completion_notes, dispatcher_addendum, created_at, updated_at) VALUES
    -- NEW orders (3)
    ('d0000001-0000-0000-0000-000000000001', 'b0000001-0000-0000-0000-000000000001', 'Annual HVAC maintenance - Building A', 'routine', CURRENT_DATE, 'morning', 'new', NULL, NULL, now() - interval '2 hours', now() - interval '2 hours'),
    ('d0000001-0000-0000-0000-000000000002', 'b0000001-0000-0000-0000-000000000002', 'AC unit not cooling - master bedroom', 'urgent', CURRENT_DATE, 'morning', 'new', NULL, NULL, now() - interval '3 hours', now() - interval '3 hours'),
    ('d0000001-0000-0000-0000-000000000003', 'b0000001-0000-0000-0000-000000000005', 'Thermostat replacement in sanctuary', 'routine', CURRENT_DATE + interval '1 day', 'afternoon', 'new', NULL, NULL, now() - interval '1 hour', now() - interval '1 hour'),

    -- ASSIGNED orders (3)
    ('d0000001-0000-0000-0000-000000000004', 'b0000001-0000-0000-0000-000000000003', 'Walk-in cooler compressor check', 'urgent', CURRENT_DATE, 'morning', 'assigned', NULL, NULL, now() - interval '4 hours', now() - interval '3 hours'),
    ('d0000001-0000-0000-0000-000000000005', 'b0000001-0000-0000-0000-000000000004', 'Furnace ignition issue - no heat', 'urgent', CURRENT_DATE, 'all_day', 'assigned', NULL, NULL, now() - interval '5 hours', now() - interval '4 hours'),
    ('d0000001-0000-0000-0000-000000000006', 'b0000001-0000-0000-0000-000000000001', 'Ductwork inspection - Floor 2', 'routine', CURRENT_DATE, 'afternoon', 'assigned', NULL, NULL, now() - interval '3 hours', now() - interval '2 hours'),

    -- IN_PROGRESS orders (4, including 1 urgent past-date for SLA breach)
    ('d0000001-0000-0000-0000-000000000007', 'b0000001-0000-0000-0000-000000000002', 'Heat pump fan motor grinding noise', 'routine', CURRENT_DATE, 'morning', 'in_progress', NULL, NULL, now() - interval '6 hours', now() - interval '1 hour'),
    ('d0000001-0000-0000-0000-000000000008', 'b0000001-0000-0000-0000-000000000003', 'Refrigerant leak in display case', 'urgent', CURRENT_DATE - interval '1 day', 'all_day', 'in_progress', NULL, NULL, now() - interval '30 hours', now() - interval '6 hours'),
    ('d0000001-0000-0000-0000-000000000009', 'b0000001-0000-0000-0000-000000000005', 'Boiler pressure relief valve replacement', 'urgent', CURRENT_DATE, 'afternoon', 'in_progress', NULL, NULL, now() - interval '5 hours', now() - interval '2 hours'),
    ('d0000001-0000-0000-0000-000000000010', 'b0000001-0000-0000-0000-000000000004', 'Condensate drain line clearing', 'routine', CURRENT_DATE, 'morning', 'in_progress', NULL, NULL, now() - interval '4 hours', now() - interval '1 hour'),

    -- COMPLETED orders (3, with notes and parts)
    ('d0000001-0000-0000-0000-000000000011', 'b0000001-0000-0000-0000-000000000001', 'Replace rooftop unit blower motor', 'urgent', CURRENT_DATE - interval '2 days', 'all_day', 'completed', 'Replaced blower motor (1/2 HP). Tested airflow at all registers. System running within spec.', NULL, now() - interval '50 hours', now() - interval '26 hours'),
    ('d0000001-0000-0000-0000-000000000012', 'b0000001-0000-0000-0000-000000000002', 'Install smart thermostat - Nest', 'routine', CURRENT_DATE - interval '3 days', 'afternoon', 'completed', 'Installed Nest Learning Thermostat 3rd gen. Configured WiFi and schedule. Customer trained on app usage.', 'Customer called back satisfied - no follow-up needed', now() - interval '80 hours', now() - interval '56 hours'),
    ('d0000001-0000-0000-0000-000000000013', 'b0000001-0000-0000-0000-000000000004', 'Furnace filter replacement and tune-up', 'routine', CURRENT_DATE - interval '4 days', 'morning', 'completed', 'Replaced 20x25x4 MERV 13 filter. Cleaned flame sensor. Checked gas pressure and heat rise.', NULL, now() - interval '100 hours', now() - interval '96 hours'),

    -- CANCELLED orders (2)
    ('d0000001-0000-0000-0000-000000000014', 'b0000001-0000-0000-0000-000000000005', 'AC install estimate - fellowship hall', 'routine', CURRENT_DATE - interval '5 days', 'morning', 'cancelled', NULL, NULL, now() - interval '130 hours', now() - interval '120 hours'),
    ('d0000001-0000-0000-0000-000000000015', 'b0000001-0000-0000-0000-000000000003', 'Emergency repair - freezer down', 'urgent', CURRENT_DATE - interval '1 day', 'morning', 'cancelled', NULL, NULL, now() - interval '30 hours', now() - interval '25 hours')
ON CONFLICT DO NOTHING;

-- ============================================================
-- Assignments (for assigned, in_progress, completed orders)
-- ============================================================
INSERT INTO assignments (id, work_order_id, technician_id, assigned_by, assigned_at, is_active) VALUES
    -- Assigned orders
    ('e0000001-0000-0000-0000-000000000001', 'd0000001-0000-0000-0000-000000000004', 'a0000001-0000-0000-0000-000000000001', 'c0000001-0000-0000-0000-000000000001', now() - interval '3 hours', true),
    ('e0000001-0000-0000-0000-000000000002', 'd0000001-0000-0000-0000-000000000005', 'a0000001-0000-0000-0000-000000000002', 'c0000001-0000-0000-0000-000000000001', now() - interval '4 hours', true),
    ('e0000001-0000-0000-0000-000000000003', 'd0000001-0000-0000-0000-000000000006', 'a0000001-0000-0000-0000-000000000003', 'c0000001-0000-0000-0000-000000000001', now() - interval '2 hours', true),
    -- In-progress orders
    ('e0000001-0000-0000-0000-000000000004', 'd0000001-0000-0000-0000-000000000007', 'a0000001-0000-0000-0000-000000000001', 'c0000001-0000-0000-0000-000000000001', now() - interval '5 hours', true),
    ('e0000001-0000-0000-0000-000000000005', 'd0000001-0000-0000-0000-000000000008', 'a0000001-0000-0000-0000-000000000002', 'c0000001-0000-0000-0000-000000000001', now() - interval '28 hours', true),
    ('e0000001-0000-0000-0000-000000000006', 'd0000001-0000-0000-0000-000000000009', 'a0000001-0000-0000-0000-000000000003', 'c0000001-0000-0000-0000-000000000001', now() - interval '4 hours', true),
    ('e0000001-0000-0000-0000-000000000007', 'd0000001-0000-0000-0000-000000000010', 'a0000001-0000-0000-0000-000000000004', 'c0000001-0000-0000-0000-000000000001', now() - interval '3 hours', true),
    -- Completed orders
    ('e0000001-0000-0000-0000-000000000008', 'd0000001-0000-0000-0000-000000000011', 'a0000001-0000-0000-0000-000000000001', 'c0000001-0000-0000-0000-000000000001', now() - interval '48 hours', true),
    ('e0000001-0000-0000-0000-000000000009', 'd0000001-0000-0000-0000-000000000012', 'a0000001-0000-0000-0000-000000000002', 'c0000001-0000-0000-0000-000000000001', now() - interval '72 hours', true),
    ('e0000001-0000-0000-0000-000000000010', 'd0000001-0000-0000-0000-000000000013', 'a0000001-0000-0000-0000-000000000003', 'c0000001-0000-0000-0000-000000000001', now() - interval '98 hours', true)
ON CONFLICT DO NOTHING;

-- ============================================================
-- Part Line Items (for completed orders - at least 2 orders with parts)
-- ============================================================
INSERT INTO part_line_items (id, work_order_id, name, quantity, unit_cost, created_at) VALUES
    -- Parts for WO 11 (rooftop blower motor)
    ('f0000001-0000-0000-0000-000000000001', 'd0000001-0000-0000-0000-000000000011', '1/2 HP Blower Motor', 1, 189.99, now() - interval '26 hours'),
    ('f0000001-0000-0000-0000-000000000002', 'd0000001-0000-0000-0000-000000000011', 'Motor mounting bracket', 1, 24.50, now() - interval '26 hours'),
    ('f0000001-0000-0000-0000-000000000003', 'd0000001-0000-0000-0000-000000000011', 'Run capacitor 10uF', 1, 12.75, now() - interval '26 hours'),
    -- Parts for WO 12 (thermostat install)
    ('f0000001-0000-0000-0000-000000000004', 'd0000001-0000-0000-0000-000000000012', 'Nest Learning Thermostat 3rd Gen', 1, 249.00, now() - interval '56 hours'),
    ('f0000001-0000-0000-0000-000000000005', 'd0000001-0000-0000-0000-000000000012', 'C-wire adapter kit', 1, 29.95, now() - interval '56 hours'),
    -- Parts for WO 13 (furnace tune-up)
    ('f0000001-0000-0000-0000-000000000006', 'd0000001-0000-0000-0000-000000000013', 'MERV 13 Filter 20x25x4', 1, 34.99, now() - interval '96 hours'),
    ('f0000001-0000-0000-0000-000000000007', 'd0000001-0000-0000-0000-000000000013', 'Flame sensor rod', 1, 8.50, now() - interval '96 hours')
ON CONFLICT DO NOTHING;

-- ============================================================
-- Audit Log (status transitions for assigned/in_progress/completed/cancelled orders)
-- ============================================================
INSERT INTO audit_log (id, work_order_id, from_status, to_status, actor_id, actor_role, changed_at) VALUES
    -- Assigned orders: new -> assigned
    ('aa000001-0000-0000-0000-000000000001', 'd0000001-0000-0000-0000-000000000004', 'new', 'assigned', 'c0000001-0000-0000-0000-000000000001', 'dispatcher', now() - interval '3 hours'),
    ('aa000001-0000-0000-0000-000000000002', 'd0000001-0000-0000-0000-000000000005', 'new', 'assigned', 'c0000001-0000-0000-0000-000000000001', 'dispatcher', now() - interval '4 hours'),
    ('aa000001-0000-0000-0000-000000000003', 'd0000001-0000-0000-0000-000000000006', 'new', 'assigned', 'c0000001-0000-0000-0000-000000000001', 'dispatcher', now() - interval '2 hours'),
    -- In-progress orders: new -> assigned -> in_progress
    ('aa000001-0000-0000-0000-000000000004', 'd0000001-0000-0000-0000-000000000007', 'new', 'assigned', 'c0000001-0000-0000-0000-000000000001', 'dispatcher', now() - interval '5 hours'),
    ('aa000001-0000-0000-0000-000000000005', 'd0000001-0000-0000-0000-000000000007', 'assigned', 'in_progress', 'c0000001-0000-0000-0000-000000000002', 'technician', now() - interval '4 hours'),
    ('aa000001-0000-0000-0000-000000000006', 'd0000001-0000-0000-0000-000000000008', 'new', 'assigned', 'c0000001-0000-0000-0000-000000000001', 'dispatcher', now() - interval '28 hours'),
    ('aa000001-0000-0000-0000-000000000007', 'd0000001-0000-0000-0000-000000000008', 'assigned', 'in_progress', 'c0000001-0000-0000-0000-000000000002', 'technician', now() - interval '26 hours'),
    ('aa000001-0000-0000-0000-000000000008', 'd0000001-0000-0000-0000-000000000009', 'new', 'assigned', 'c0000001-0000-0000-0000-000000000001', 'dispatcher', now() - interval '4 hours'),
    ('aa000001-0000-0000-0000-000000000009', 'd0000001-0000-0000-0000-000000000009', 'assigned', 'in_progress', 'c0000001-0000-0000-0000-000000000002', 'technician', now() - interval '3 hours'),
    ('aa000001-0000-0000-0000-000000000010', 'd0000001-0000-0000-0000-000000000010', 'new', 'assigned', 'c0000001-0000-0000-0000-000000000001', 'dispatcher', now() - interval '3 hours'),
    ('aa000001-0000-0000-0000-000000000011', 'd0000001-0000-0000-0000-000000000010', 'assigned', 'in_progress', 'c0000001-0000-0000-0000-000000000002', 'technician', now() - interval '2 hours'),
    -- Completed orders: full lifecycle
    ('aa000001-0000-0000-0000-000000000012', 'd0000001-0000-0000-0000-000000000011', 'new', 'assigned', 'c0000001-0000-0000-0000-000000000001', 'dispatcher', now() - interval '48 hours'),
    ('aa000001-0000-0000-0000-000000000013', 'd0000001-0000-0000-0000-000000000011', 'assigned', 'in_progress', 'c0000001-0000-0000-0000-000000000002', 'technician', now() - interval '30 hours'),
    ('aa000001-0000-0000-0000-000000000014', 'd0000001-0000-0000-0000-000000000011', 'in_progress', 'completed', 'c0000001-0000-0000-0000-000000000002', 'technician', now() - interval '26 hours'),
    ('aa000001-0000-0000-0000-000000000015', 'd0000001-0000-0000-0000-000000000012', 'new', 'assigned', 'c0000001-0000-0000-0000-000000000001', 'dispatcher', now() - interval '72 hours'),
    ('aa000001-0000-0000-0000-000000000016', 'd0000001-0000-0000-0000-000000000012', 'assigned', 'in_progress', 'c0000001-0000-0000-0000-000000000002', 'technician', now() - interval '60 hours'),
    ('aa000001-0000-0000-0000-000000000017', 'd0000001-0000-0000-0000-000000000012', 'in_progress', 'completed', 'c0000001-0000-0000-0000-000000000002', 'technician', now() - interval '56 hours'),
    ('aa000001-0000-0000-0000-000000000018', 'd0000001-0000-0000-0000-000000000013', 'new', 'assigned', 'c0000001-0000-0000-0000-000000000001', 'dispatcher', now() - interval '98 hours'),
    ('aa000001-0000-0000-0000-000000000019', 'd0000001-0000-0000-0000-000000000013', 'assigned', 'in_progress', 'c0000001-0000-0000-0000-000000000002', 'technician', now() - interval '97 hours'),
    ('aa000001-0000-0000-0000-000000000020', 'd0000001-0000-0000-0000-000000000013', 'in_progress', 'completed', 'c0000001-0000-0000-0000-000000000002', 'technician', now() - interval '96 hours'),
    -- Cancelled orders
    ('aa000001-0000-0000-0000-000000000021', 'd0000001-0000-0000-0000-000000000014', 'new', 'cancelled', 'c0000001-0000-0000-0000-000000000001', 'dispatcher', now() - interval '120 hours'),
    ('aa000001-0000-0000-0000-000000000022', 'd0000001-0000-0000-0000-000000000015', 'new', 'cancelled', 'c0000001-0000-0000-0000-000000000001', 'dispatcher', now() - interval '25 hours')
ON CONFLICT DO NOTHING;
