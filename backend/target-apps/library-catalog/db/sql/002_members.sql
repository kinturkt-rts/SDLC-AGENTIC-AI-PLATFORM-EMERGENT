-- Members table: Library members with email and member_key authentication
CREATE TABLE IF NOT EXISTS members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL UNIQUE,
    member_key VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Indexes for efficient member lookups and authentication
CREATE INDEX IF NOT EXISTS idx_members_email ON members (email);
CREATE INDEX IF NOT EXISTS idx_members_key ON members (member_key);
CREATE INDEX IF NOT EXISTS idx_members_created_at ON members (created_at);

-- Comments for documentation
COMMENT ON TABLE members IS 'Library members with email uniqueness and member_key auth';
COMMENT ON COLUMN members.member_key IS 'Auto-generated key for header-based authentication';
COMMENT ON COLUMN members.email IS 'Corporate email address with uniqueness constraint';