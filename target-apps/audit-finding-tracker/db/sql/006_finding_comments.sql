-- 006_finding_comments.sql: Threaded discussion support for findings
-- Enables collaboration with parent-child comment relationships

CREATE TABLE IF NOT EXISTS finding_comments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    finding_id UUID NOT NULL REFERENCES findings(id) ON DELETE CASCADE,
    author_id UUID NOT NULL REFERENCES users(id),
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    parent_id UUID REFERENCES finding_comments(id)
);

-- Indexes for efficient comment queries
CREATE INDEX IF NOT EXISTS idx_comments_finding_created ON finding_comments(finding_id, created_at);
CREATE INDEX IF NOT EXISTS idx_comments_author_id ON finding_comments(author_id);
CREATE INDEX IF NOT EXISTS idx_comments_parent_id ON finding_comments(parent_id);