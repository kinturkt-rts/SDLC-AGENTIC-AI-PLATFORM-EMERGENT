-- 002_users.sql
SET search_path TO support_knowledge_hub, public;

CREATE TABLE IF NOT EXISTS users (
    id              uuid PRIMARY KEY,
    email           text NOT NULL UNIQUE,
    display_name    text NOT NULL,
    role            text NOT NULL CHECK (role IN ('employee','contributor','knowledge_admin','leadership')),
    hashed_password text NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);
