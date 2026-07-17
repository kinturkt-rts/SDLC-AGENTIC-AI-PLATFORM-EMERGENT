-- 003_create_users.sql
-- Users table for Field Service Dispatch (auth + RBAC)

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username TEXT NOT NULL UNIQUE,
    hashed_password TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('dispatcher', 'technician', 'owner')),
    technician_id UUID REFERENCES technicians(id)
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users (username);
