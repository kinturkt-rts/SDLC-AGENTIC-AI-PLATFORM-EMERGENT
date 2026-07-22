-- 011_seed.sql
-- Dev/test seed data for meeting-room-api
-- Host replaces __SHA256_PLACEHOLDER:<label>__ with sha256(plaintext).hexdigest()
-- API key for demo-standard: "demo-standard-key-2024"
-- API key for demo-admin: "demo-admin-key-2024"
-- API key for alice-integration: "demo-alice-key-2024"
-- API key for bob-ci-testing: "demo-bob-key-2024"
-- API key for facilities-ops: "demo-facilities-key-2024"

-- =============================================================================
-- Rooms (7 rows)
-- =============================================================================
INSERT INTO rooms (id, name, floor, capacity, amenities, active, created_at, updated_at) VALUES
    ('a1000001-0000-0000-0000-000000000001', 'Board Room', '1', 10, 'Projector, Whiteboard, Video Conferencing', true, '2024-01-15 09:00:00+00', '2024-01-15 09:00:00+00'),
    ('a1000001-0000-0000-0000-000000000002', 'Focus Pod', '2', 4, 'Whiteboard', true, '2024-01-15 09:00:00+00', '2024-01-15 09:00:00+00'),
    ('a1000001-0000-0000-0000-000000000003', 'Town Hall', '3', 50, 'Stage, Projector, PA System, Video Conferencing', true, '2024-01-15 09:00:00+00', '2024-01-15 09:00:00+00'),
    ('a1000001-0000-0000-0000-000000000004', 'Huddle Space A', '1', 6, 'TV Screen, Whiteboard', true, '2024-02-01 10:00:00+00', '2024-02-01 10:00:00+00'),
    ('a1000001-0000-0000-0000-000000000005', 'Huddle Space B', '2', 6, 'TV Screen', true, '2024-02-01 10:00:00+00', '2024-02-01 10:00:00+00'),
    ('a1000001-0000-0000-0000-000000000006', 'Executive Suite', '4', 12, 'Projector, Video Conferencing, Catering Station', true, '2024-03-01 08:00:00+00', '2024-03-01 08:00:00+00'),
    ('a1000001-0000-0000-0000-000000000007', 'Training Lab', '3', 30, 'Projector, Whiteboard, Individual Desks', false, '2024-01-20 09:00:00+00', '2024-06-01 14:00:00+00')
ON CONFLICT (id) DO NOTHING;

-- =============================================================================
-- Reservations (8 rows — spread across rooms, organizers, statuses)
-- Using future dates relative to a 2025 baseline
-- =============================================================================
INSERT INTO reservations (id, room_id, title, organizer_email, start_time, end_time, notes, status, created_at, updated_at, cancelled_at) VALUES
    ('b2000001-0000-0000-0000-000000000001', 'a1000001-0000-0000-0000-000000000001', 'Q3 Planning Review', 'alice@company.com', '2025-09-10 09:00:00+00', '2025-09-10 10:30:00+00', 'Bring printed agendas', 'active', '2025-08-01 08:00:00+00', '2025-08-01 08:00:00+00', NULL),
    ('b2000001-0000-0000-0000-000000000002', 'a1000001-0000-0000-0000-000000000002', 'Design Sprint Kickoff', 'bob@company.com', '2025-09-11 14:00:00+00', '2025-09-11 15:00:00+00', NULL, 'active', '2025-08-02 10:00:00+00', '2025-08-02 10:00:00+00', NULL),
    ('b2000001-0000-0000-0000-000000000003', 'a1000001-0000-0000-0000-000000000003', 'All-Hands September', 'ceo@company.com', '2025-09-15 16:00:00+00', '2025-09-15 17:30:00+00', 'Company-wide update', 'active', '2025-08-05 09:00:00+00', '2025-08-05 09:00:00+00', NULL),
    ('b2000001-0000-0000-0000-000000000004', 'a1000001-0000-0000-0000-000000000004', '1:1 with Manager', 'dave@company.com', '2025-09-12 11:00:00+00', '2025-09-12 11:30:00+00', NULL, 'active', '2025-08-03 12:00:00+00', '2025-08-03 12:00:00+00', NULL),
    ('b2000001-0000-0000-0000-000000000005', 'a1000001-0000-0000-0000-000000000005', 'Interview - Backend Engineer', 'hr@company.com', '2025-09-13 10:00:00+00', '2025-09-13 11:00:00+00', 'Candidate: Jane Smith', 'active', '2025-08-04 14:00:00+00', '2025-08-04 14:00:00+00', NULL),
    ('b2000001-0000-0000-0000-000000000006', 'a1000001-0000-0000-0000-000000000001', 'Budget Review (Cancelled)', 'alice@company.com', '2025-09-08 13:00:00+00', '2025-09-08 14:00:00+00', 'Moved to next week', 'cancelled', '2025-07-30 09:00:00+00', '2025-08-06 10:00:00+00', '2025-08-06 10:00:00+00'),
    ('b2000001-0000-0000-0000-000000000007', 'a1000001-0000-0000-0000-000000000006', 'Client Demo Prep', 'eve@company.com', '2025-09-16 09:00:00+00', '2025-09-16 11:00:00+00', 'Dry run for Friday demo', 'active', '2025-08-07 08:30:00+00', '2025-08-07 08:30:00+00', NULL),
    ('b2000001-0000-0000-0000-000000000008', 'a1000001-0000-0000-0000-000000000003', 'Fire Safety Training', 'facilities@company.com', '2025-09-20 14:00:00+00', '2025-09-20 16:00:00+00', 'Mandatory attendance for floor wardens', 'active', '2025-08-10 11:00:00+00', '2025-08-10 11:00:00+00', NULL)
ON CONFLICT (id) DO NOTHING;

-- =============================================================================
-- API Keys (5 rows — SHA-256 digests materialized by host from comments above)
-- =============================================================================
INSERT INTO api_keys (id, key_hash, role, label, active, created_at) VALUES
    ('c3000001-0000-0000-0000-000000000001', '__SHA256_PLACEHOLDER:demo-standard__', 'standard', 'demo-standard', true, '2024-01-15 09:00:00+00'),
    ('c3000001-0000-0000-0000-000000000002', '__SHA256_PLACEHOLDER:demo-admin__', 'admin', 'demo-admin', true, '2024-01-15 09:00:00+00'),
    ('c3000001-0000-0000-0000-000000000003', '__SHA256_PLACEHOLDER:alice-integration__', 'standard', 'alice-integration', true, '2024-02-10 10:00:00+00'),
    ('c3000001-0000-0000-0000-000000000004', '__SHA256_PLACEHOLDER:bob-ci-testing__', 'standard', 'bob-ci-testing', true, '2024-03-05 14:00:00+00'),
    ('c3000001-0000-0000-0000-000000000005', '__SHA256_PLACEHOLDER:facilities-ops__', 'admin', 'facilities-ops', true, '2024-04-01 08:00:00+00')
ON CONFLICT (id) DO NOTHING;
