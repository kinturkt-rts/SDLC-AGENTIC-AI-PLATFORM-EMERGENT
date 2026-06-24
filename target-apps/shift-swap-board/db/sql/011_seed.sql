-- Password for all seed users: "Password1!"
-- 011_seed.sql — Dev/test fixture data for shift_swap_board
SET search_path = shift_swap_board;

-- ============================================================
-- USERS (9 total: 1 admin, 2 floor_leads, 6 staff)
-- ============================================================
INSERT INTO users (id, username, password_hash, role, display_name, is_active, created_at) VALUES
    ('a0000000-0000-0000-0000-000000000001', 'admin',    '__BCRYPT_PLACEHOLDER__', 'admin',      'Alice Admin',    true, now() - interval '30 days'),
    ('a0000000-0000-0000-0000-000000000002', 'lead_a',   '__BCRYPT_PLACEHOLDER__', 'floor_lead', 'Leo Lead',       true, now() - interval '28 days'),
    ('a0000000-0000-0000-0000-000000000003', 'lead_b',   '__BCRYPT_PLACEHOLDER__', 'floor_lead', 'Lena Boswell',   true, now() - interval '28 days'),
    ('a0000000-0000-0000-0000-000000000004', 'staff_01', '__BCRYPT_PLACEHOLDER__', 'staff',      'Sam Taylor',     true, now() - interval '25 days'),
    ('a0000000-0000-0000-0000-000000000005', 'staff_02', '__BCRYPT_PLACEHOLDER__', 'staff',      'Dana Rivera',    true, now() - interval '25 days'),
    ('a0000000-0000-0000-0000-000000000006', 'staff_03', '__BCRYPT_PLACEHOLDER__', 'staff',      'Chris Park',     true, now() - interval '25 days'),
    ('a0000000-0000-0000-0000-000000000007', 'staff_04', '__BCRYPT_PLACEHOLDER__', 'staff',      'Morgan Blake',   true, now() - interval '20 days'),
    ('a0000000-0000-0000-0000-000000000008', 'staff_05', '__BCRYPT_PLACEHOLDER__', 'staff',      'Jordan Casey',   true, now() - interval '20 days'),
    ('a0000000-0000-0000-0000-000000000009', 'staff_06', '__BCRYPT_PLACEHOLDER__', 'staff',      'Riley Nguyen',   true, now() - interval '20 days')
ON CONFLICT DO NOTHING;

-- ============================================================
-- STAFF_PROFILES (one per staff + floor_lead users = 8)
-- ============================================================
INSERT INTO staff_profiles (id, user_id, employee_code) VALUES
    ('b0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000002', 'EMP-100'),
    ('b0000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000003', 'EMP-101'),
    ('b0000000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000004', 'EMP-200'),
    ('b0000000-0000-0000-0000-000000000004', 'a0000000-0000-0000-0000-000000000005', 'EMP-201'),
    ('b0000000-0000-0000-0000-000000000005', 'a0000000-0000-0000-0000-000000000006', 'EMP-202'),
    ('b0000000-0000-0000-0000-000000000006', 'a0000000-0000-0000-0000-000000000007', 'EMP-203'),
    ('b0000000-0000-0000-0000-000000000007', 'a0000000-0000-0000-0000-000000000008', 'EMP-204'),
    ('b0000000-0000-0000-0000-000000000008', 'a0000000-0000-0000-0000-000000000009', 'EMP-205')
ON CONFLICT DO NOTHING;

-- ============================================================
-- FLOOR_LEAD_WEEKS (current + next Monday)
-- ============================================================
INSERT INTO floor_lead_weeks (id, week_start, floor_lead_user_id) VALUES
    ('c0000000-0000-0000-0000-000000000001', date_trunc('week', CURRENT_DATE)::date, 'a0000000-0000-0000-0000-000000000002'),
    ('c0000000-0000-0000-0000-000000000002', (date_trunc('week', CURRENT_DATE) + interval '7 days')::date, 'a0000000-0000-0000-0000-000000000003')
ON CONFLICT DO NOTHING;

-- ============================================================
-- SHIFT_ROSTER (~12 rows across next 7 days)
-- ============================================================
INSERT INTO shift_roster (id, staff_id, shift_date, shift_window, created_at) VALUES
    ('d0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000003', CURRENT_DATE + 1, 'morning',   now()),
    ('d0000000-0000-0000-0000-000000000002', 'b0000000-0000-0000-0000-000000000004', CURRENT_DATE + 1, 'afternoon', now()),
    ('d0000000-0000-0000-0000-000000000003', 'b0000000-0000-0000-0000-000000000005', CURRENT_DATE + 1, 'full',      now()),
    ('d0000000-0000-0000-0000-000000000004', 'b0000000-0000-0000-0000-000000000006', CURRENT_DATE + 2, 'morning',   now()),
    ('d0000000-0000-0000-0000-000000000005', 'b0000000-0000-0000-0000-000000000007', CURRENT_DATE + 2, 'afternoon', now()),
    ('d0000000-0000-0000-0000-000000000006', 'b0000000-0000-0000-0000-000000000008', CURRENT_DATE + 2, 'full',      now()),
    ('d0000000-0000-0000-0000-000000000007', 'b0000000-0000-0000-0000-000000000003', CURRENT_DATE + 3, 'afternoon', now()),
    ('d0000000-0000-0000-0000-000000000008', 'b0000000-0000-0000-0000-000000000004', CURRENT_DATE + 3, 'morning',   now()),
    ('d0000000-0000-0000-0000-000000000009', 'b0000000-0000-0000-0000-000000000005', CURRENT_DATE + 4, 'morning',   now()),
    ('d0000000-0000-0000-0000-000000000010', 'b0000000-0000-0000-0000-000000000006', CURRENT_DATE + 5, 'afternoon', now()),
    ('d0000000-0000-0000-0000-000000000011', 'b0000000-0000-0000-0000-000000000007', CURRENT_DATE + 5, 'full',      now()),
    ('d0000000-0000-0000-0000-000000000012', 'b0000000-0000-0000-0000-000000000001', CURRENT_DATE + 6, 'morning',   now())
ON CONFLICT DO NOTHING;

-- ============================================================
-- SWAP_REQUESTS (3: open, claimed, approved)
-- ============================================================
INSERT INTO swap_requests (id, offered_shift_id, offered_by_user_id, status, claimed_by_user_id, claimed_at, decided_by_user_id, decided_at, decision_note, created_at, updated_at) VALUES
    -- open swap (staff_01 offers their morning shift on CURRENT_DATE+1)
    ('e0000000-0000-0000-0000-000000000001',
     'd0000000-0000-0000-0000-000000000001',
     'a0000000-0000-0000-0000-000000000004',
     'open', NULL, NULL, NULL, NULL, NULL,
     now() - interval '2 hours', now() - interval '2 hours'),
    -- claimed swap (staff_02 offers their afternoon shift on CURRENT_DATE+1, staff_03 claimed)
    ('e0000000-0000-0000-0000-000000000002',
     'd0000000-0000-0000-0000-000000000002',
     'a0000000-0000-0000-0000-000000000005',
     'claimed', 'a0000000-0000-0000-0000-000000000006', now() - interval '30 minutes', NULL, NULL, NULL,
     now() - interval '3 hours', now() - interval '30 minutes'),
    -- approved swap (staff_04 offered morning on CURRENT_DATE+2, staff_05 claimed, lead_a approved)
    ('e0000000-0000-0000-0000-000000000003',
     'd0000000-0000-0000-0000-000000000004',
     'a0000000-0000-0000-0000-000000000007',
     'approved', 'a0000000-0000-0000-0000-000000000008', now() - interval '5 hours', 'a0000000-0000-0000-0000-000000000002', now() - interval '1 hour', 'Coverage confirmed',
     now() - interval '6 hours', now() - interval '1 hour')
ON CONFLICT DO NOTHING;

-- ============================================================
-- SWAP_AUDIT_LOG (audit trail for the 3 swaps above)
-- ============================================================
INSERT INTO swap_audit_log (id, swap_request_id, action, actor_user_id, detail, created_at) VALUES
    -- open swap: created
    ('f0000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000001', 'created', 'a0000000-0000-0000-0000-000000000004', '{"from_status":null,"to_status":"open"}', now() - interval '2 hours'),
    -- claimed swap: created + claimed
    ('f0000000-0000-0000-0000-000000000002', 'e0000000-0000-0000-0000-000000000002', 'created', 'a0000000-0000-0000-0000-000000000005', '{"from_status":null,"to_status":"open"}', now() - interval '3 hours'),
    ('f0000000-0000-0000-0000-000000000003', 'e0000000-0000-0000-0000-000000000002', 'claimed', 'a0000000-0000-0000-0000-000000000006', '{"from_status":"open","to_status":"claimed"}', now() - interval '30 minutes'),
    -- approved swap: created + claimed + approved + roster_updated
    ('f0000000-0000-0000-0000-000000000004', 'e0000000-0000-0000-0000-000000000003', 'created', 'a0000000-0000-0000-0000-000000000007', '{"from_status":null,"to_status":"open"}', now() - interval '6 hours'),
    ('f0000000-0000-0000-0000-000000000005', 'e0000000-0000-0000-0000-000000000003', 'claimed', 'a0000000-0000-0000-0000-000000000008', '{"from_status":"open","to_status":"claimed"}', now() - interval '5 hours'),
    ('f0000000-0000-0000-0000-000000000006', 'e0000000-0000-0000-0000-000000000003', 'approved', 'a0000000-0000-0000-0000-000000000002', '{"from_status":"claimed","to_status":"approved"}', now() - interval '1 hour'),
    ('f0000000-0000-0000-0000-000000000007', 'e0000000-0000-0000-0000-000000000003', 'roster_updated', 'a0000000-0000-0000-0000-000000000002', '{"offerer_shift_removed":"d0000000-0000-0000-0000-000000000004","accepter_shift_added":true}', now() - interval '1 hour')
ON CONFLICT DO NOTHING;
