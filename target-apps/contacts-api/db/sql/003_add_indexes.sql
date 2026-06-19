-- 003_add_indexes.sql
-- Create indexes for performance according to design §6

-- Create pg_trgm extension first (required for trigram search indexes)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Index on contacts email for uniqueness and search performance
CREATE UNIQUE INDEX IF NOT EXISTS idx_contacts_email ON contacts (email) WHERE email IS NOT NULL;

-- Index on department_id for foreign key joins
CREATE INDEX IF NOT EXISTS idx_contacts_department_id ON contacts (department_id);

-- Index on is_active for filtering active contacts
CREATE INDEX IF NOT EXISTS idx_contacts_is_active ON contacts (is_active);

-- Composite index for search functionality on full_name and email
CREATE INDEX IF NOT EXISTS idx_contacts_search ON contacts USING gin ((full_name || ' ' || COALESCE(email, '')) gin_trgm_ops);