-- Loans table: Book checkout tracking with date-aware business logic
CREATE TABLE IF NOT EXISTS loans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    book_id UUID NOT NULL REFERENCES books(id) ON DELETE RESTRICT,
    member_id UUID NOT NULL REFERENCES members(id) ON DELETE RESTRICT,
    checkout_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    due_at TIMESTAMP WITH TIME ZONE NOT NULL,
    returned_at TIMESTAMP WITH TIME ZONE NULL
);

-- Unique constraint: one active loan per book-member pair
CREATE UNIQUE INDEX IF NOT EXISTS idx_loans_active_book_member 
    ON loans (book_id, member_id) 
    WHERE returned_at IS NULL;

-- Indexes for efficient queries on loans and overdue calculations
CREATE INDEX IF NOT EXISTS idx_loans_book_member ON loans (book_id, member_id);
CREATE INDEX IF NOT EXISTS idx_loans_due_at ON loans (due_at);
CREATE INDEX IF NOT EXISTS idx_loans_returned_at ON loans (returned_at);
CREATE INDEX IF NOT EXISTS idx_loans_member_active ON loans (member_id) WHERE returned_at IS NULL;

-- Comments for documentation
COMMENT ON TABLE loans IS 'Book checkout records with date tracking and overdue logic';
COMMENT ON COLUMN loans.due_at IS 'Calculated from checkout_at + LOAN_DAYS environment variable';
COMMENT ON COLUMN loans.returned_at IS 'NULL for active loans, timestamp when returned';
COMMENT ON CONSTRAINT idx_loans_active_book_member ON loans IS 'Prevents double-checkout of same book by same member';