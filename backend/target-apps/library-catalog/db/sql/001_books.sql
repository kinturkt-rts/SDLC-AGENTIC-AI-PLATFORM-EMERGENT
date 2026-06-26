-- Books table: Core book catalog with copy tracking
CREATE TABLE IF NOT EXISTS books (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    isbn VARCHAR(20) NOT NULL UNIQUE,
    title VARCHAR(500) NOT NULL,
    author VARCHAR(300) NOT NULL,
    total_copies INTEGER NOT NULL DEFAULT 1 CHECK (total_copies >= 0),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Indexes for efficient book search and lookups
CREATE INDEX IF NOT EXISTS idx_books_isbn ON books (isbn);
CREATE INDEX IF NOT EXISTS idx_books_title_author ON books (title, author);
CREATE INDEX IF NOT EXISTS idx_books_created_at ON books (created_at);

-- Comments for documentation
COMMENT ON TABLE books IS 'Book catalog with ISBN uniqueness and copy tracking';
COMMENT ON COLUMN books.total_copies IS 'Total physical copies available for checkout';
COMMENT ON COLUMN books.isbn IS 'ISBN-10 or ISBN-13 with uniqueness constraint';