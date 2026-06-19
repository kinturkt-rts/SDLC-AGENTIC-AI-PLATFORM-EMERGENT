-- Seed data for api_keys table
INSERT INTO api_keys (key_hash, name, created_at, is_active) VALUES
('sha256:demo_key_hash_123456789abcdef', 'Demo API Key', '2024-01-15 10:00:00+00:00', true),
('sha256:test_key_hash_987654321fedcba', 'Test Environment Key', '2024-01-15 11:00:00+00:00', true),
('sha256:manager_key_hash_abc123def456', 'Engineering Manager Key', '2024-01-16 09:00:00+00:00', true),
('sha256:lead_key_hash_def456abc123', 'Tech Lead Key', '2024-01-16 14:30:00+00:00', true),
('sha256:dev_key_hash_456def123abc', 'Senior Developer Key', '2024-01-17 08:15:00+00:00', true),
('sha256:inactive_key_hash_789ghi456jkl', 'Inactive Key', '2024-01-10 16:45:00+00:00', false)
ON CONFLICT (key_hash) DO NOTHING;

-- Seed data for reviews table
INSERT INTO reviews (id, submitted_at, title, diff_text, file_count, lines_added, lines_removed, summary, risk_score, risk_band, model_id, created_by) VALUES
('550e8400-e29b-41d4-a716-446655440001', '2024-01-18 10:30:00+00:00', 'Add user authentication middleware', 
'diff --git a/app/middleware/auth.py b/app/middleware/auth.py
new file mode 100644
index 0000000..abc123
--- /dev/null
+++ b/app/middleware/auth.py
@@ -0,0 +1,25 @@
+from fastapi import HTTPException, Request
+def authenticate_request(request: Request):
+    api_key = request.headers.get("X-API-Key")
+    if not api_key or not validate_key(api_key):
+        raise HTTPException(status_code=401)', 
3, 25, 0, 'Adds authentication middleware with API key validation. Creates new auth module with request validation function and HTTP exception handling for unauthorized access.', 35, 'medium', 'claude-3-sonnet-20240229', 'manager@example.com'),

('550e8400-e29b-41d4-a716-446655440002', '2024-01-18 14:15:00+00:00', 'Database migration for user roles',
'diff --git a/migrations/001_add_user_roles.sql b/migrations/001_add_user_roles.sql
new file mode 100644
index 0000000..def456
--- /dev/null
+++ b/migrations/001_add_user_roles.sql
@@ -0,0 +1,15 @@
+CREATE TABLE user_roles (
+    id SERIAL PRIMARY KEY,
+    role_name VARCHAR(50) NOT NULL
+);
+INSERT INTO user_roles VALUES (1, "admin");',
1, 15, 0, 'Database migration adding user roles table with primary key and role name column. Includes initial admin role insertion for access control setup.', 85, 'high', 'claude-3-sonnet-20240229', 'lead@example.com'),

('550e8400-e29b-41d4-a716-446655440003', '2024-01-19 09:45:00+00:00', 'Fix typo in README',
'diff --git a/README.md b/README.md
index 123..456
--- a/README.md
+++ b/README.md
@@ -12,1 +12,1 @@
-This is a exmaple of usage
+This is an example of usage',
1, 1, 1, 'Minor documentation fix correcting a typo in the README file. Changes "exmaple" to "example" for proper spelling and readability.', 15, 'low', 'claude-3-sonnet-20240229', 'dev@example.com'),

('550e8400-e29b-41d4-a716-446655440004', '2024-01-19 16:20:00+00:00', 'Refactor API response handling',
'diff --git a/app/api/handlers.py b/app/api/handlers.py
index 789..012
--- a/app/api/handlers.py
+++ b/app/api/handlers.py
@@ -45,10 +45,15 @@
-def handle_response(data):
-    return {"status": "success", "data": data}
+def handle_response(data, status_code=200):
+    response = {"status": "success" if status_code < 400 else "error"}
+    if data:
+        response["data"] = data
+    return response, status_code',
1, 8, 3, 'Refactors API response handler to support flexible status codes and conditional data inclusion. Improves error handling by setting status based on HTTP code.', 42, 'medium', 'claude-3-sonnet-20240229', 'lead@example.com'),

('550e8400-e29b-41d4-a716-446655440005', '2024-01-20 11:00:00+00:00', 'Add environment configuration',
'diff --git a/config/settings.py b/config/settings.py
new file mode 100644
index 0000000..345abc
--- /dev/null
+++ b/config/settings.py
@@ -0,0 +1,12 @@
+import os
+DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost/app")
+SECRET_KEY = os.getenv("SECRET_KEY", "default-secret")
+DEBUG = os.getenv("DEBUG", "false").lower() == "true"
+API_RATE_LIMIT = int(os.getenv("API_RATE_LIMIT", "100"))',
1, 12, 0, 'Adds environment-based configuration system with database URL, secret key, debug mode and API rate limiting. Uses secure defaults and environment variable overrides.', 55, 'medium', 'claude-3-sonnet-20240229', 'manager@example.com'),

('550e8400-e29b-41d4-a716-446655440006', '2024-01-20 15:30:00+00:00', 'Security update: hash sensitive data',
'diff --git a/app/utils/security.py b/app/utils/security.py
index 567..890
--- a/app/utils/security.py
+++ b/app/utils/security.py
@@ -8,5 +8,12 @@
+import hashlib
+import secrets
+
+def hash_api_key(key: str) -> str:
+    salt = secrets.token_hex(16)
+    return hashlib.pbkdf2_hmac("sha256", key.encode(), salt.encode(), 100000)',
1, 7, 0, 'Implements secure API key hashing using PBKDF2 with SHA-256 and random salt generation. Adds cryptographic security for sensitive authentication data storage.', 78, 'high', 'claude-3-sonnet-20240229', 'dev@example.com'),

('550e8400-e29b-41d4-a716-446655440007', '2024-01-21 08:45:00+00:00', 'Update dependency versions',
'diff --git a/requirements.txt b/requirements.txt
index abc..def
--- a/requirements.txt
+++ b/requirements.txt
@@ -3,3 +3,3 @@
-fastapi==0.68.0
-uvicorn==0.15.0
+fastapi==0.104.1
+uvicorn==0.24.0',
1, 2, 2, 'Updates FastAPI and Uvicorn to latest stable versions for security patches and performance improvements. No breaking changes expected in migration.', 25, 'low', 'claude-3-sonnet-20240229', 'dev@example.com')
ON CONFLICT (id) DO NOTHING;