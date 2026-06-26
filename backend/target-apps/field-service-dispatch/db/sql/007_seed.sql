-- Seed: dev/test fixture data for field_service_dispatch
-- Password for all seed users: "Dispatch123!"
-- This file is idempotent (ON CONFLICT DO NOTHING).
-- Host runs materialize_seed_passwords.py after apply to replace __BCRYPT_PLACEHOLDER__.

SET search_path TO field_service_dispatch;

-- ============================================================
-- Technicians (7 rows — varied skills, 1 inactive)
-- ============================================================
INSERT INTO technicians (id, display_name, skills, is_active) VALUES
    ('a1000000-0000-0000-0000-000000000001', 'Marcus Johnson', ARRAY['residential','install'], true),
    ('a1000000-0000-0000-0000-000000000002', 'Keisha Williams', ARRAY['commercial','refrigeration'], true),
    ('a1000000-0000-0000-0000-000000000003', 'Carlos Rivera', ARRAY['residential','commercial'], true),
    ('a1000000-0000-0000-0000-000000000004', 'Tanya Patel', ARRAY['install','refrigeration'], true),
    ('a1000000-0000-0000-0000-000000000005', 'Derek Brooks', ARRAY['residential'], true),
    ('a1000000-0000-0000-0000-000000000006', 'Lisa Chen', ARRAY['commercial','install'], true),
    ('a1000000-0000-0000-0000-000000000007', 'James Okafor', ARRAY['residential','refrigeration'], false)
ON CONFLICT DO NOTHING;

-- ============================================================
-- Users (10 rows — 2 dispatchers, 1 owner, 7 technician accounts)
-- ============================================================
INSERT INTO users (id, username, hashed_password, role, technician_id) VALUES
    ('b1000000-0000-0000-0000-000000000001', 'dana', '__BCRYPT_PLACEHOLDER__', 'dispatcher', NULL),
    ('b1000000-0000-0000-0000-000000000002', 'sam', '__BCRYPT_PLACEHOLDER__', 'dispatcher', NULL),
    ('b1000000-0000-0000-0000-000000000003', 'owner_pat', '__BCRYPT_PLACEHOLDER__', 'owner', NULL),
    ('b1000000-0000-0000-0000-000000000004', 'tech_marcus', '__BCRYPT_PLACEHOLDER__', 'technician', 'a1000000-0000-0000-0000-000000000001'),
    ('b1000000-0000-0000-0000-000000000005', 'tech_keisha', '__BCRYPT_PLACEHOLDER__', 'technician', 'a1000000-0000-0000-0000-000000000002'),
    ('b1000000-0000-0000-0000-000000000006', 'tech_carlos', '__BCRYPT_PLACEHOLDER__', 'technician', 'a1000000-0000-0000-0000-000000000003'),
    ('b1000000-0000-0000-0000-000000000007', 'tech_tanya', '__BCRYPT_PLACEHOLDER__', 'technician', 'a1000000-0000-0000-0000-000000000004'),
    ('b1000000-0000-0000-0000-000000000008', 'tech_derek', '__BCRYPT_PLACEHOLDER__', 'technician', 'a1000000-0000-0000-0000-000000000005'),
    ('b1000000-0000-0000-0000-000000000009', 'tech_lisa', '__BCRYPT_PLACEHOLDER__', 'technician', 'a1000000-0000-0000-0000-000000000006'),
    ('b1000000-0000-0000-0000-000000000010', 'tech_james', '__BCRYPT_PLACEHOLDER__', 'technician', 'a1000000-0000-0000-0000-000000000007')
ON CONFLICT DO NOTHING;

-- ============================================================
-- Customers (8 rows)
-- ============================================================
INSERT INTO customers (id, full_name, phone, email, is_active, created_at) VALUES
    ('c1000000-0000-0000-0000-000000000001', 'Riverside Office Park LLC', '555-100-2001', 'facilities@riverside.example.com', true, '2024-11-01 08:00:00-05'),
    ('c1000000-0000-0000-0000-000000000002', 'Maria Gonzalez', '555-100-2002', 'maria.g@example.com', true, '2024-11-02 09:15:00-05'),
    ('c1000000-0000-0000-0000-000000000003', 'Thompson Family', '555-100-2003', NULL, true, '2024-11-03 10:30:00-05'),
    ('c1000000-0000-0000-0000-000000000004', 'City Diner', '555-100-2004', 'info@citydiner.example.com', true, '2024-11-04 11:00:00-05'),
    ('c1000000-0000-0000-0000-000000000005', 'Angela Brooks', '555-100-2005', 'abrooks@example.com', true, '2024-11-05 14:00:00-05'),
    ('c1000000-0000-0000-0000-000000000006', 'Summit Church', '555-100-2006', 'office@summitchurch.example.com', true, '2024-11-06 08:45:00-05'),
    ('c1000000-0000-0000-0000-000000000007', 'Dave Park', '555-100-2007', NULL, true, '2024-11-07 16:00:00-05'),
    ('c1000000-0000-0000-0000-000000000008', 'Lakewood Apartments', '555-100-2008', 'maint@lakewood.example.com', false, '2024-10-15 09:00:00-05')
ON CONFLICT DO NOTHING;

-- ============================================================
-- Service Addresses (10 rows)
-- ============================================================
INSERT INTO service_addresses (id, customer_id, street, city, state, postal_code) VALUES
    ('d1000000-0000-0000-0000-000000000001', 'c1000000-0000-0000-0000-000000000001', '200 River Rd', 'Columbus', 'OH', '43215'),
    ('d1000000-0000-0000-0000-000000000002', 'c1000000-0000-0000-0000-000000000001', '210 River Rd Suite B', 'Columbus', 'OH', '43215'),
    ('d1000000-0000-0000-0000-000000000003', 'c1000000-0000-0000-0000-000000000002', '45 Maple St', 'Westerville', 'OH', '43081'),
    ('d1000000-0000-0000-0000-000000000004', 'c1000000-0000-0000-0000-000000000003', '789 Oak Ln', 'Dublin', 'OH', '43017'),
    ('d1000000-0000-0000-0000-000000000005', 'c1000000-0000-0000-0000-000000000004', '12 Main St', 'Columbus', 'OH', '43201'),
    ('d1000000-0000-0000-0000-000000000006', 'c1000000-0000-0000-0000-000000000005', '330 Elm Ave', 'Gahanna', 'OH', '43230'),
    ('d1000000-0000-0000-0000-000000000007', 'c1000000-0000-0000-0000-000000000006', '500 Faith Dr', 'Hilliard', 'OH', '43026'),
    ('d1000000-0000-0000-0000-000000000008', 'c1000000-0000-0000-0000-000000000007', '88 Pine Ct', 'Reynoldsburg', 'OH', '43068'),
    ('d1000000-0000-0000-0000-000000000009', 'c1000000-0000-0000-0000-000000000008', '1400 Lakewood Blvd Unit 1', 'Columbus', 'OH', '43204'),
    ('d1000000-0000-0000-0000-000000000010', 'c1000000-0000-0000-0000-000000000008', '1400 Lakewood Blvd Unit 12', 'Columbus', 'OH', '43204')
ON CONFLICT DO NOTHING;

-- ============================================================
-- Work Orders (15 rows — covers all statuses, SLA breach, etc.)
-- Uses CURRENT_DATE for scheduled_date so SLA breaches are always visible.
-- ============================================================
INSERT INTO work_orders (id, customer_id, description, priority, scheduled_date, time_window, status, assigned_technician_id, completion_notes, created_at, updated_at) VALUES
    -- NEW (unassigned)
    ('e1000000-0000-0000-0000-000000000001', 'c1000000-0000-0000-0000-000000000001', 'Annual HVAC inspection — Building A rooftop units', 'routine', CURRENT_DATE, 'morning', 'new', NULL, NULL, now() - interval '2 hours', now() - interval '2 hours'),
    ('e1000000-0000-0000-0000-000000000002', 'c1000000-0000-0000-0000-000000000003', 'Thermostat not responding — second floor', 'routine', CURRENT_DATE, 'afternoon', 'new', NULL, NULL, now() - interval '1 hour', now() - interval '1 hour'),
    ('e1000000-0000-0000-0000-000000000003', 'c1000000-0000-0000-0000-000000000007', 'Filter replacement — whole house', 'routine', CURRENT_DATE + 1, 'all_day', 'new', NULL, NULL, now() - interval '30 minutes', now() - interval '30 minutes'),

    -- ASSIGNED
    ('e1000000-0000-0000-0000-000000000004', 'c1000000-0000-0000-0000-000000000002', 'AC blowing warm air — living room unit', 'urgent', CURRENT_DATE, 'morning', 'assigned', 'a1000000-0000-0000-0000-000000000001', NULL, now() - interval '3 hours', now() - interval '2 hours'),
    ('e1000000-0000-0000-0000-000000000005', 'c1000000-0000-0000-0000-000000000004', 'Walk-in cooler temperature alarm', 'urgent', CURRENT_DATE, 'morning', 'assigned', 'a1000000-0000-0000-0000-000000000002', NULL, now() - interval '4 hours', now() - interval '3 hours'),
    ('e1000000-0000-0000-0000-000000000006', 'c1000000-0000-0000-0000-000000000006', 'Sanctuary HVAC making grinding noise', 'routine', CURRENT_DATE, 'afternoon', 'assigned', 'a1000000-0000-0000-0000-000000000003', NULL, now() - interval '5 hours', now() - interval '4 hours'),

    -- IN_PROGRESS
    ('e1000000-0000-0000-0000-000000000007', 'c1000000-0000-0000-0000-000000000005', 'No heat — furnace pilot light out', 'urgent', CURRENT_DATE, 'morning', 'in_progress', 'a1000000-0000-0000-0000-000000000004', NULL, now() - interval '6 hours', now() - interval '1 hour'),
    ('e1000000-0000-0000-0000-000000000008', 'c1000000-0000-0000-0000-000000000001', 'Replace condenser fan motor — Unit 3', 'routine', CURRENT_DATE, 'all_day', 'in_progress', 'a1000000-0000-0000-0000-000000000005', NULL, now() - interval '7 hours', now() - interval '2 hours'),

    -- COMPLETED (with notes; 2 will have parts)
    ('e1000000-0000-0000-0000-000000000009', 'c1000000-0000-0000-0000-000000000002', 'Ductwork leak repair — basement', 'routine', CURRENT_DATE - 1, 'morning', 'completed', 'a1000000-0000-0000-0000-000000000001', 'Sealed two duct joints with mastic sealant. Tested airflow — normal.', now() - interval '1 day', now() - interval '20 hours'),
    ('e1000000-0000-0000-0000-000000000010', 'c1000000-0000-0000-0000-000000000004', 'Refrigerant recharge — walk-in freezer', 'urgent', CURRENT_DATE - 1, 'afternoon', 'completed', 'a1000000-0000-0000-0000-000000000002', 'Recharged R-404A to spec. Checked for leaks with electronic detector — none found.', now() - interval '1 day', now() - interval '18 hours'),
    ('e1000000-0000-0000-0000-000000000011', 'c1000000-0000-0000-0000-000000000005', 'Install programmable thermostat', 'routine', CURRENT_DATE - 2, 'afternoon', 'completed', 'a1000000-0000-0000-0000-000000000006', 'Installed Honeywell T6 Pro. Configured schedules with customer. Old mercury thermostat disposed.', now() - interval '2 days', now() - interval '44 hours'),

    -- CANCELLED
    ('e1000000-0000-0000-0000-000000000012', 'c1000000-0000-0000-0000-000000000003', 'Vent cleaning — whole house', 'routine', CURRENT_DATE - 1, 'all_day', 'cancelled', NULL, NULL, now() - interval '2 days', now() - interval '1 day'),

    -- SLA-BREACHED URGENT (scheduled yesterday, still assigned — not completed)
    ('e1000000-0000-0000-0000-000000000013', 'c1000000-0000-0000-0000-000000000006', 'Emergency — no AC in fellowship hall during event', 'urgent', CURRENT_DATE - 1, 'morning', 'assigned', 'a1000000-0000-0000-0000-000000000003', NULL, now() - interval '1 day', now() - interval '1 day'),

    -- Additional variety
    ('e1000000-0000-0000-0000-000000000014', 'c1000000-0000-0000-0000-000000000008', 'Unit 12 — replace evaporator coil', 'routine', CURRENT_DATE + 2, 'all_day', 'new', NULL, NULL, now() - interval '10 minutes', now() - interval '10 minutes'),
    ('e1000000-0000-0000-0000-000000000015', 'c1000000-0000-0000-0000-000000000007', 'Outdoor unit vibration — compressor mount check', 'routine', CURRENT_DATE, 'afternoon', 'assigned', 'a1000000-0000-0000-0000-000000000005', NULL, now() - interval '3 hours', now() - interval '2 hours')
ON CONFLICT DO NOTHING;

-- ============================================================
-- Work Order Parts (6 rows — for completed orders e1..09, e1..10, e1..11)
-- ============================================================
INSERT INTO work_order_parts (id, work_order_id, part_name, quantity, unit_cost) VALUES
    ('f1000000-0000-0000-0000-000000000001', 'e1000000-0000-0000-0000-000000000009', 'Mastic sealant tube', 2, 8.50),
    ('f1000000-0000-0000-0000-000000000002', 'e1000000-0000-0000-0000-000000000009', 'Foil-backed tape 30yd', 1, 12.99),
    ('f1000000-0000-0000-0000-000000000003', 'e1000000-0000-0000-0000-000000000010', 'R-404A refrigerant 25lb cylinder', 1, 189.00),
    ('f1000000-0000-0000-0000-000000000004', 'e1000000-0000-0000-0000-000000000010', 'Schrader valve core', 2, 3.75),
    ('f1000000-0000-0000-0000-000000000005', 'e1000000-0000-0000-0000-000000000011', 'Honeywell T6 Pro thermostat', 1, 74.99),
    ('f1000000-0000-0000-0000-000000000006', 'e1000000-0000-0000-0000-000000000011', 'Thermostat wire 18/5 50ft', 1, 22.50)
ON CONFLICT DO NOTHING;

-- ============================================================
-- Status History (representative transitions — 10 rows)
-- ============================================================
INSERT INTO status_history (id, work_order_id, actor_user_id, actor_role, previous_status, new_status, context_note, changed_at) VALUES
    -- WO-04 new -> assigned
    ('aa000000-0000-0000-0000-000000000001', 'e1000000-0000-0000-0000-000000000004', 'b1000000-0000-0000-0000-000000000001', 'dispatcher', 'new', 'assigned', 'Assigned to Marcus — closest to location', now() - interval '2 hours'),
    -- WO-05 new -> assigned
    ('aa000000-0000-0000-0000-000000000002', 'e1000000-0000-0000-0000-000000000005', 'b1000000-0000-0000-0000-000000000001', 'dispatcher', 'new', 'assigned', 'Keisha has refrigeration cert', now() - interval '3 hours'),
    -- WO-06 new -> assigned
    ('aa000000-0000-0000-0000-000000000003', 'e1000000-0000-0000-0000-000000000006', 'b1000000-0000-0000-0000-000000000002', 'dispatcher', 'new', 'assigned', NULL, now() - interval '4 hours'),
    -- WO-07 new -> assigned -> in_progress
    ('aa000000-0000-0000-0000-000000000004', 'e1000000-0000-0000-0000-000000000007', 'b1000000-0000-0000-0000-000000000001', 'dispatcher', 'new', 'assigned', 'Urgent — Tanya dispatched immediately', now() - interval '5 hours'),
    ('aa000000-0000-0000-0000-000000000005', 'e1000000-0000-0000-0000-000000000007', 'b1000000-0000-0000-0000-000000000007', 'technician', 'assigned', 'in_progress', 'On site', now() - interval '1 hour'),
    -- WO-09 new -> assigned -> in_progress -> completed
    ('aa000000-0000-0000-0000-000000000006', 'e1000000-0000-0000-0000-000000000009', 'b1000000-0000-0000-0000-000000000001', 'dispatcher', 'new', 'assigned', NULL, now() - interval '25 hours'),
    ('aa000000-0000-0000-0000-000000000007', 'e1000000-0000-0000-0000-000000000009', 'b1000000-0000-0000-0000-000000000004', 'technician', 'assigned', 'in_progress', NULL, now() - interval '23 hours'),
    ('aa000000-0000-0000-0000-000000000008', 'e1000000-0000-0000-0000-000000000009', 'b1000000-0000-0000-0000-000000000004', 'technician', 'in_progress', 'completed', 'Job done — sealant cure 24h', now() - interval '20 hours'),
    -- WO-12 new -> cancelled
    ('aa000000-0000-0000-0000-000000000009', 'e1000000-0000-0000-0000-000000000012', 'b1000000-0000-0000-0000-000000000001', 'dispatcher', 'new', 'cancelled', 'Customer rescheduled to next month', now() - interval '1 day'),
    -- WO-13 new -> assigned (SLA breach — still assigned from yesterday)
    ('aa000000-0000-0000-0000-000000000010', 'e1000000-0000-0000-0000-000000000013', 'b1000000-0000-0000-0000-000000000002', 'dispatcher', 'new', 'assigned', 'Carlos assigned — urgent church event', now() - interval '1 day')
ON CONFLICT DO NOTHING;
