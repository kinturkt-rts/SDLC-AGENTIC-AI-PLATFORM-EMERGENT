-- Password for standard seed api_key: "dev-standard-key"
-- Password for admin seed api_key: "dev-admin-key"
--
-- 011_seed.sql
-- Dev/test fixture data for bug-deduper
-- api_keys: real bcrypt hashes (key_hash is UNIQUE — one row per distinct key)

SET search_path TO bug_deduper, public;

-- ============================================================
-- API Keys (2 rows — design §6.2)
-- ============================================================
INSERT INTO bug_deduper.api_keys (id, key_hash, tier, created_at) VALUES
    (
        'a1000000-0000-0000-0000-000000000001',
        '$2b$12$brF6ENk7eoFj2kGQrXAxq.T5VImjH2HvBlzstsTSLsADRBb3YFk/i',
        'standard',
        '2024-01-10 08:00:00+00'
    ),
    (
        'a1000000-0000-0000-0000-000000000002',
        '$2b$12$CY/SpU.YbRfWnZfDz978Ge1Q/q3OJgTCFfWowk1IiLXQEIJ11l3YW',
        'admin',
        '2024-01-13 11:00:00+00'
    )
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- Bugs (7 rows — zero-vector embeddings for local dev smoke tests)
-- ============================================================
INSERT INTO bug_deduper.bugs (id, title, description, embedding, status, duplicate_of, created_at, updated_at) VALUES
    (
        'b2000000-0000-0000-0000-000000000001',
        'Login page returns 500 error on Chrome',
        'When clicking the Sign In button on Chrome v120, the page returns an HTTP 500 Internal Server Error. The server logs show a NullPointerException in AuthService.authenticate().',
        (SELECT ('[' || array_to_string(array_fill(0::float, ARRAY[1024]), ',') || ']')::vector),
        'open',
        NULL,
        '2024-02-01 10:00:00+00',
        '2024-02-01 10:00:00+00'
    ),
    (
        'b2000000-0000-0000-0000-000000000002',
        'Sign-in button triggers server error in Chrome browser',
        'Attempting to authenticate via the Sign In button on Chrome results in a 500 status code. Stack trace references a null pointer in the authentication service layer.',
        (SELECT ('[' || array_to_string(array_fill(0::float, ARRAY[1024]), ',') || ']')::vector),
        'open',
        NULL,
        '2024-02-02 11:00:00+00',
        '2024-02-02 11:00:00+00'
    ),
    (
        'b2000000-0000-0000-0000-000000000003',
        'Dashboard chart renders blank on Firefox',
        'The analytics dashboard pie chart component does not render any data on Firefox 121. The canvas element is present but empty. Works fine on Chromium-based browsers.',
        (SELECT ('[' || array_to_string(array_fill(0::float, ARRAY[1024]), ',') || ']')::vector),
        'open',
        NULL,
        '2024-02-03 14:30:00+00',
        '2024-02-03 14:30:00+00'
    ),
    (
        'b2000000-0000-0000-0000-000000000004',
        'CSV export includes deleted records',
        'Exporting the user list as CSV includes rows for soft-deleted users that should be filtered out. The export query does not apply the is_deleted flag filter.',
        (SELECT ('[' || array_to_string(array_fill(0::float, ARRAY[1024]), ',') || ']')::vector),
        'open',
        NULL,
        '2024-02-04 09:15:00+00',
        '2024-02-04 09:15:00+00'
    ),
    (
        'b2000000-0000-0000-0000-000000000005',
        'Memory leak in WebSocket connection handler',
        'The real-time notification WebSocket handler does not release connection objects on client disconnect. After ~200 concurrent users, the service OOMs and restarts.',
        (SELECT ('[' || array_to_string(array_fill(0::float, ARRAY[1024]), ',') || ']')::vector),
        'open',
        NULL,
        '2024-02-05 16:00:00+00',
        '2024-02-05 16:00:00+00'
    ),
    (
        'b2000000-0000-0000-0000-000000000006',
        'Login error 500 on Chrome — duplicate of BUG-001',
        'Clicking Sign In on Chrome gives a 500 error. Auth service throws NPE. Same root cause as the earlier login bug.',
        (SELECT ('[' || array_to_string(array_fill(0::float, ARRAY[1024]), ',') || ']')::vector),
        'duplicate',
        'b2000000-0000-0000-0000-000000000001',
        '2024-02-06 08:45:00+00',
        '2024-02-06 09:00:00+00'
    ),
    (
        'b2000000-0000-0000-0000-000000000007',
        'Password reset email not sent for SSO users',
        'Users with SSO-linked accounts who request a password reset never receive the email. The PasswordResetService skips sending when sso_provider is non-null but should still allow local reset.',
        (SELECT ('[' || array_to_string(array_fill(0::float, ARRAY[1024]), ',') || ']')::vector),
        'resolved',
        NULL,
        '2024-01-20 12:00:00+00',
        '2024-02-07 10:00:00+00'
    )
ON CONFLICT (id) DO NOTHING;
