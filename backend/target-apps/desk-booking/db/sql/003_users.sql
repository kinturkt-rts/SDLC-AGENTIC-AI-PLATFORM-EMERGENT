-- Migration 003: Create users table
-- Employee user accounts with authentication tokens

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    user_token TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Index on user_token for authentication lookups
CREATE INDEX IF NOT EXISTS idx_users_user_token ON users (user_token);

-- Index on email for user lookups
CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);