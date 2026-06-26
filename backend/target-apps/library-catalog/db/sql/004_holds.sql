-- Holds table: FIFO queue management for book reservations
CREATE TABLE IF NOT EXISTS holds (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    book_id UUID NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    member_id UUID NOT NULL REFERENCES members(id) ON DELETE CASCADE,
    placed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    fulfilled_at TIMESTAMP WITH TIME ZONE NULL,
    cancelled_at TIMESTAMP WITH TIME ZONE NULL
);

-- Unique constraint: one active hold per book-member pair
CREATE UNIQUE INDEX IF NOT EXISTS idx_holds_active_book_member 
    ON holds (book_id, member_id) 
    WHERE fulfilled_at IS NULL AND cancelled_at IS NULL;

-- Indexes for FIFO queue processing and member lookups
CREATE INDEX IF NOT EXISTS idx_holds_book_placed ON holds (book_id, placed_at);
CREATE INDEX IF NOT EXISTS idx_holds_member ON holds (member_id);
CREATE INDEX IF NOT EXISTS idx_holds_active_by_book ON holds (book_id, placed_at) 
    WHERE fulfilled_at IS NULL AND cancelled_at IS NULL;

-- Comments for documentation
COMMENT ON TABLE holds IS 'FIFO hold queue for unavailable books';
COMMENT ON COLUMN holds.placed_at IS 'Timestamp for FIFO queue ordering';
COMMENT ON COLUMN holds.fulfilled_at IS 'NULL for active holds, set when auto-fulfilled on return';
COMMENT ON COLUMN holds.cancelled_at IS 'Timestamp when member or librarian cancels hold';
COMMENT ON CONSTRAINT idx_holds_active_book_member ON holds IS 'Prevents duplicate active holds by same member';